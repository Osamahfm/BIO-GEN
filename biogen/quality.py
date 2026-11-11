"""Measured visual indicators, not a disease diagnosis or chemical assay."""
import threading
import cv2
import numpy as np
from PIL import Image, ImageOps
from plantcv import plantcv as pcv

from .part_profiles import normalize_part

LOCK = threading.Lock()  # PlantCV observations are process-global.


def current_for_part(result, plant_part):
    part = normalize_part(plant_part or 'leaves')
    return bool(result) and result.get('plant_part', 'leaves') == part


def analyse(path, output_path, plant_part='leaves'):
    part = normalize_part(plant_part or 'leaves')
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert('RGB')
    original_size = image.size
    image.thumbnail((1200, 1200))
    rgb = np.asarray(image)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    dark = float((gray < 20).mean())
    bright = float((gray > 250).mean())
    indicators = {'image_width': original_size[0], 'image_height': original_size[1],
                  'analysed_width': image.width, 'analysed_height': image.height,
                  'sharpness_variance': round(sharpness, 2),
                  'dark_pixel_percent': round(dark * 100, 2), 'bright_pixel_percent': round(bright * 100, 2)}
    flags = []
    if min(original_size) < 256:
        flags.append({'code': 'small_image', 'critical': True, 'message': 'Image is smaller than 256 pixels on one side. Upload a larger image.'})
    if sharpness < 40:
        flags.append({'code': 'blur', 'critical': True, 'message': 'Low sharpness under the prototype threshold; capture a sharper image.'})
    if dark > .45:
        flags.append({'code': 'exposure', 'critical': part == 'leaves',
                      'message': 'A large part of the image is very dark. Review lighting and specimen visibility.'})

    if part != 'leaves':
        return {'plant_part': part, 'engine': 'OpenCV', 'method': 'Whole-image resolution, sharpness and brightness checks',
                'metrics': indicators, 'flags': flags, 'overlay': None,
                'status': 'review_required' if flags else 'visual_checks_passed',
                'limitations': ['Measurements include the specimen and background. Review the image to judge specimen visibility.',
                                'These checks assess the photograph. Review specimen condition separately.']}

    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
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
        seeds[:3, :] = seeds[-3:, :] = cv2.GC_BGD
        seeds[:, :3] = seeds[:, -3:] = cv2.GC_BGD
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
    if coverage < .03 or coverage > .95:
        flags.append({'code': 'segmentation', 'critical': True, 'message': 'Foreground mask is unreliable. Use one leaf on a plain neutral background.'})
    if pixels.any():
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
            flags.append({'code': 'discoloration', 'critical': False, 'message': 'Visible yellow/brown tissue exceeds the prototype threshold; plant-scientist review suggested.'})
    else:
        discoloured = pixels
    overlay = rgb.copy()
    overlay[pixels] = (rgb[pixels] * .65 + np.array([35, 213, 150]) * .35).astype('uint8')
    overlay[discoloured] = (rgb[discoloured] * .5 + np.array([255, 163, 50]) * .5).astype('uint8')
    Image.fromarray(overlay).save(output_path)
    return {'plant_part': part, 'engine': 'PlantCV + OpenCV', 'method': 'PlantCV saturation threshold + green-anchored GrabCut + largest connected foreground + PlantCV HSV analysis',
            'metrics': indicators, 'flags': flags, 'overlay': output_path.name,
            'status': 'review_required' if flags else 'visual_checks_passed',
            'limitations': ['Thresholds are prototype settings, not clinically or botanically validated cutoffs.',
                           'A mask may include background objects; inspect the overlay.',
                           'Green anchoring can miss fully yellow/brown tissue; foreground area is not total specimen area.',
                           'No specific disease, chemical purity, or phytochemical abundance is inferred.']}
