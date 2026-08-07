import pickle
from pathlib import Path


def save_model(model: object, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as stream:
        pickle.dump(model, stream)
    return target


def load_model(path: str | Path) -> object:
    with Path(path).open("rb") as stream:
        return pickle.load(stream)
