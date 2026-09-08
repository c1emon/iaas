"""Build-stage pruning; preserve executable resources and license metadata."""

from pathlib import Path
import shutil


def remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


# Retain Debian redistribution notices separately before dropping manuals.
for notice in Path('/usr/share/doc').glob('*/copyright'):
    destination = Path('/usr/share/licenses/debian') / notice.parent.name
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(notice, destination / 'copyright')

for root in [Path('/opt/iaas'), Path('/usr/local/lib/python3.12'), Path('/etc'), Path('/usr/share')]:
    for path in sorted(root.rglob('*'), key=lambda p: len(p.parts), reverse=True):
        # doc_fragments and plugin/module source are required Ansible resources.
        if path.name in {'test', 'tests'} and path.parent.name == 'plugins':
            continue
        if path.name in {'tests', 'test', '__pycache__', 'docs', 'examples', 'fixtures', 'openspec', '.github', '.git', '.gitnexus'}:
            remove(path)
        elif path.name.lower().startswith(('readme', 'changelog')) or path.name == 'AGENTS.md' or path.suffix == '.pyc':
            remove(path)

for name in ['/usr/share/doc', '/usr/share/man', '/usr/share/info', '/usr/local/include',
             '/usr/include', '/root/.cache', '/root/.ansible', '/tmp/collections.yml',
             '/tmp/prune.py']:
    remove(Path(name))
for pattern in ['pip*', 'setuptools*', 'wheel*']:
    for path in Path('/usr/local/lib/python3.12/site-packages').glob(pattern):
        remove(path)
for path in Path('/usr/local/bin').glob('pip*'):
    remove(path)
