"""Train an actual Ayur-Ai ResNet18 head on frozen ImageNet features.

Source photos are grouped by perceptual hash before train/validation/test splitting.
Model selection uses validation only. Final test is reported once, separately.
This is an internal prototype benchmark; same-plant/collection leakage may remain.
"""
import argparse
import copy
import hashlib
import json
import os
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'vendor/ayur-ai'))
os.environ.setdefault('TORCH_HOME', str(ROOT / 'models/torch-cache'))


def prepare():
    archive = ROOT / 'data/downloads/medicinal-leaves.zip'
    target = ROOT / 'data/training/leaves'
    if not archive.exists():
        raise FileNotFoundError('Download the CC BY dataset first; see docs/MODEL.md')
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            p = Path(item.filename)
            if p.suffix.lower() not in ('.jpg', '.jpeg', '.png'):
                continue
            # Only the species and filename are retained; never extract archive paths.
            species = p.parts[-2]
            if species in ('.', '..') or '/' in species or '\\' in species:
                raise ValueError('Unsafe archive class name')
            dest = target / species / p.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                dest.write_bytes(z.read(item))
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--epochs', type=int, default=150)
    args = parser.parse_args()
    import numpy as np
    import torch
    from torch.utils.data import DataLoader, Subset
    from torchvision.datasets import ImageFolder
    from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix
    from src.config import Config
    from src.data import inference_transform, _component_stratified_split
    from src.model import build_model, save_checkpoint

    torch.set_num_threads(args.threads)
    torch.manual_seed(42)
    np.random.seed(42)
    started = time.time()
    folder = prepare()
    cfg = Config.load(overrides={'data.raw_dir': str(folder), 'data.num_workers': 0,
                               'data.image_size': 160, 'model.freeze_backbone': True,
                               'train.checkpoint_path': str(ROOT / 'models/plant_model.pt')})
    dataset = ImageFolder(str(folder), transform=inference_transform(cfg.data.image_size))
    print(f'{len(dataset)} source images, {len(dataset.classes)} dataset labels', flush=True)
    train, val, test = _component_stratified_split(dataset.samples, .15, .15, 42)
    print(f'Grouped split: train={len(train)} validation={len(val)} test={len(test)}', flush=True)
    net = build_model('resnet18', len(dataset.classes), pretrained=True, freeze_backbone=True)
    head = net.fc
    net.fc = torch.nn.Identity()
    net.eval()
    features = []
    with torch.no_grad():
        for i, (images, _) in enumerate(DataLoader(dataset, batch_size=48, num_workers=0)):
            features.append(net(images).cpu())
            if i % 10 == 0:
                print(f'Feature extraction {min((i+1)*48,len(dataset))}/{len(dataset)}', flush=True)
    x = torch.cat(features)
    y = torch.tensor(dataset.targets)
    train, val, test = list(train), list(val), list(test)
    if not train or not val or not test:
        raise ValueError('Grouped split produced an empty subset. Inspect the dataset grouping.')
    optimizer = torch.optim.AdamW(head.parameters(), lr=.01, weight_decay=.01)
    loss_fn = torch.nn.CrossEntropyLoss()
    best_loss, best, history = float('inf'), None, []
    for epoch in range(args.epochs):
        head.train()
        order = torch.randperm(len(train)).tolist()
        for start in range(0, len(order), 128):
            ids = [train[j] for j in order[start:start+128]]
            optimizer.zero_grad()
            loss = loss_fn(head(x[ids]), y[ids])
            loss.backward()
            optimizer.step()
        head.eval()
        with torch.no_grad():
            logits = head(x[val])
            vl = loss_fn(logits, y[val]).item()
            acc = (logits.argmax(1) == y[val]).float().mean().item()
        history.append({'epoch': epoch+1, 'val_loss': vl, 'val_accuracy': acc})
        if vl < best_loss:
            best_loss, best = vl, copy.deepcopy(head.state_dict())
        if epoch % 25 == 0:
            print(f'Head epoch {epoch+1}: val accuracy={acc:.4f}, loss={vl:.4f}', flush=True)
    head.load_state_dict(best)
    head.eval()
    with torch.no_grad():
        predicted = head(x[test]).argmax(1).numpy()
    truth = y[test].numpy()
    net.fc = head
    save_checkpoint(cfg.checkpoint_path, net, dataset.classes, cfg,
                    extra={'dataset': '10.17632/748f8jkphb.3', 'frozen_backbone': True, 'split_seed': 42})
    model_file = cfg.checkpoint_path
    report = {'ready': True, 'architecture': 'Ayur-Ai ResNet18 + trained linear classification head',
              'training_method': 'Frozen ImageNet backbone, cached features, AdamW head training; validation-loss checkpoint selection',
              'classes': dataset.classes, 'source_images': len(dataset),
              'split': {'train': len(train), 'validation': len(val), 'test': len(test)},
              'test_accuracy': float(accuracy_score(truth, predicted)),
              'test_macro_f1': float(f1_score(truth, predicted, labels=list(range(len(dataset.classes))), average='macro', zero_division=0)),
              'test_classification_report': classification_report(truth, predicted, labels=list(range(len(dataset.classes))), target_names=dataset.classes, output_dict=True, zero_division=0),
              'confusion_matrix': confusion_matrix(truth, predicted, labels=list(range(len(dataset.classes)))).tolist(),
              'dataset_url': 'https://www.kaggle.com/datasets/warcoder/indian-medicinal-plant-image-dataset',
              'original_dataset_doi': 'https://doi.org/10.17632/748f8jkphb.3', 'dataset_license': 'CC BY 4.0',
              'sha256': hashlib.sha256(model_file.read_bytes()).hexdigest(),
              'elapsed_seconds': round(time.time()-started, 1),
              'limitations': ['Internal grouped image test only; not field validation.', 'Perceptual hashing reduces near-duplicate leakage but does not establish independent plants or collection sites.', 'Class labels are dataset labels; scientific identity still requires researcher confirmation.', 'Scores are uncalibrated; unsupported species may receive confident predictions.', 'These are species labels, not disease or chemical-quality labels.']}
    (ROOT / 'models/identification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (ROOT / 'models/training-history.json').write_text(json.dumps(history, indent=2), encoding='utf-8')
    split_manifest = {name: [{'path': str(Path(dataset.samples[i][0]).relative_to(folder)), 'label': dataset.classes[dataset.targets[i]]} for i in ids] for name, ids in [('train',train),('validation',val),('test',test)]}
    (ROOT / 'models/split-manifest.json').write_text(json.dumps(split_manifest, indent=2), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['test_accuracy','test_macro_f1','split','elapsed_seconds']}), flush=True)


if __name__ == '__main__':
    main()
