"""Measured visual indicators, not a disease diagnosis or chemical assay."""
import threading
import cv2
import numpy as np
from PIL import Image, ImageOps
from plantcv import plantcv as pcv

from .part_profiles import normalize_part

LOCK = threading.Lock()  # PlantCV observations are process-global.
MASK_BORDER = 3


def current_for_part(result, plant_part):
    part = normalize_part(plant_part or 'leaves')
    return bool(result) and result.get('plant_part', 'leaves') == part


def analyse(path, output_path, plant_part='leaves', outline=None):
    part = normalize_part(plant_part or 'leaves')
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert('RGB')
    original_size = image.size
    image.thumbnail((1200, 1200))
    rgb = np.asarray(image)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    dark = float((gray < 20).mean())
    bright = float((gray > 250).mean())
    low_tone, high_tone = np.percentile(gray, [5, 95])
    indicators = {'image_width': original_size[0], 'image_height': original_size[1],
                  'analysed_width': image.width, 'analysed_height': image.height,
                  'dark_pixel_percent': round(dark * 100, 2), 'bright_pixel_percent': round(bright * 100, 2)}
    flags = []
    if min(original_size) < 256:
        flags.append({'code': 'small_image', 'critical': True, 'message': 'Upload a photo with at least 256 pixels on each side.'})
    if high_tone - low_tone < 15:
        flags.append({'code': 'low_contrast', 'critical': True, 'message': 'The photo has very little contrast. Retake it with even lighting and a background that contrasts with the specimen.'})
    if dark > .45:
        flags.append({'code': 'exposure', 'critical': part == 'leaves',
                      'message': 'Much of the photo is very dark. Check that shadows do not hide the specimen. Use even lighting if you retake it.'})
    if bright > .90:
        flags.append({'code': 'bright_exposure', 'critical': False,
                      'message': 'Most pixels are near white. Check whether glare or a bright background obscures the specimen.'})

    if part != 'leaves':
        return {'plant_part': part, 'engine': 'OpenCV', 'method': 'Whole-image resolution, contrast and exposure checks',
                'metrics': indicators, 'flags': flags, 'overlay': None,
                'status': 'review_required' if flags else 'visual_checks_passed',
                'limitations': ['Measurements include the specimen and background. Review the image to judge specimen visibility.',
                                'These checks assess the photograph. Review specimen condition separately.']}

    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    if outline:
        vertices = np.rint(np.asarray(outline) * [image.width - 1, image.height - 1]).astype(np.int32)
        if abs(cv2.contourArea(vertices)) < 16:
            raise ValueError('Mark points around the leaf so the outline encloses an area.')
        mask = np.zeros_like(gray)
        cv2.fillPoly(mask, [vertices], 255)
    else:
        # PlantCV supplies the colour threshold; green anchors initialise GrabCut.
        # This heuristic can miss fully yellow/brown leaves and needs mask inspection.
        with LOCK:
            pcv.params.debug = None
            mask = pcv.threshold.binary(gray_img=hsv[:, :, 1], threshold=45, object_type='light')
            mask = pcv.fill(bin_img=mask, size=150)
        green = (mask > 0) & (hsv[:, :, 0] >= 35) & (hsv[:, :, 0] <= 100) & (hsv[:, :, 2] > 35)
        if green.sum() >= 100:
            seeds = np.full(gray.shape, cv2.GC_PR_BGD, dtype='uint8')
            seeds[green] = cv2.GC_PR_FGD
            core = cv2.erode(green.astype('uint8'), np.ones((3, 3), 'uint8')) > 0
            seeds[core] = cv2.GC_FGD
            seeds[:MASK_BORDER, :] = seeds[-MASK_BORDER:, :] = cv2.GC_BGD
            seeds[:, :MASK_BORDER] = seeds[:, -MASK_BORDER:] = cv2.GC_BGD
            if (seeds == cv2.GC_FGD).any():
                cv2.grabCut(rgb, seeds, None, np.zeros((1, 65)), np.zeros((1, 65)), 3, cv2.GC_INIT_WITH_MASK)
                mask = np.where((seeds == cv2.GC_FGD) | (seeds == cv2.GC_PR_FGD), 255, 0).astype('uint8')
            else:
                mask = green.astype('uint8') * 255
        else:
            mask = np.zeros_like(gray)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype('uint8'), 8)
        if count > 1:
            i = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
            mask = np.where(labels == i, 255, 0).astype('uint8')
    pixels = mask > 0
    coverage = float(pixels.mean())
    indicators['foreground_percent'] = round(coverage * 100, 2)
    reliable_coverage = bool(outline) or .03 <= coverage <= .95
    touches_frame = False
    if not reliable_coverage:
        framing = ('The detected leaf area is too small.' if coverage < .03
                   else 'The detected leaf area covers almost the entire frame.')
        flags.append({'code': 'segmentation', 'critical': True,
                      'message': f'{framing} Photograph one leaf on a plain contrasting background with space around it.'})
    elif not outline and min(gray.shape) > 2 * MASK_BORDER:
        edge = MASK_BORDER
        edge_contacts = (pixels[edge, :].sum(), pixels[-edge - 1, :].sum(),
                         pixels[:, edge].sum(), pixels[:, -edge - 1].sum())
        touches_frame = max(edge_contacts) > .02 * min(gray.shape)
        if touches_frame:
            flags.append({'code': 'framing', 'critical': False,
                          'message': 'The detected area reaches the frame edge and may include nearby leaves or miss part of the target leaf. Photograph one leaf on a plain contrasting background with space around it.'})
    if reliable_coverage and not touches_frame:
        # HSV yellow/brown is a visual proxy only, sensitive to lighting and species.
        discoloured = pixels & (hsv[:, :, 0] < 35) & (hsv[:, :, 1] > 60)
        fraction = float(discoloured.sum() / pixels.sum())
        indicators['yellow_brown_percent'] = round(fraction * 100, 2)
        with LOCK:
            pcv.outputs.clear()
            pcv.analyze.color(rgb_img=rgb, labeled_mask=pixels.astype('int32'), colorspaces='hsv')
            # Store a stable numeric summary alongside PlantCV's actual computation.
            observations = pcv.outputs.observations
            indicators['plantcv_observation_fields'] = {str(k): list(v) for k, v in observations.items()}
        if fraction > .25:
            flags.append({'code': 'discoloration', 'critical': False,
                          'message': 'Yellow or brown areas cover more than 25% of the detected leaf. Compare the overlay with the original and inspect those areas.'})
    else:
        discoloured = np.zeros_like(pixels)
    overlay = rgb.copy()
    overlay[pixels] = (rgb[pixels] * .65 + np.array([35, 213, 150]) * .35).astype('uint8')
    overlay[discoloured] = (rgb[discoloured] * .5 + np.array([255, 163, 50]) * .5).astype('uint8')
    Image.fromarray(overlay).save(output_path)
    method = ('Researcher-drawn leaf outline + PlantCV HSV analysis' if outline else
              'PlantCV saturation threshold + green-anchored GrabCut + largest connected foreground + PlantCV HSV analysis')
    return {'plant_part': part, 'engine': 'PlantCV + OpenCV', 'method': method, 'outline': outline,
            'metrics': indicators, 'flags': flags, 'overlay': output_path.name,
            'status': 'review_required' if flags else 'visual_checks_passed',
            'limitations': ['Thresholds are prototype settings, not clinically or botanically validated cutoffs.',
                           'A mask may include background objects; inspect the overlay.',
                           ('The colour measurement depends on the accuracy of the drawn outline.' if outline else
                            'Green anchoring can miss fully yellow/brown tissue; foreground area is not total specimen area.'),
                           'No specific disease, chemical purity, or phytochemical abundance is inferred.']}
