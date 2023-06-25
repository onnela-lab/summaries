from __future__ import annotations
import json
import numpy as np
from pathlib import Path
import pickle
import pytest
from sklearn.linear_model import LinearRegression
from summaries.scripts.infer import __main__, INFERENCE_CONFIGS, InferenceConfig
from summaries.scripts.preprocess_coal import __main__ as __main__preprocess_coal
from summaries.transformers import as_transformer, MinimumConditionalEntropyTransformer, \
    NeuralTransformer, Transformer
from torch import nn
from typing import Any, Dict, Type
from unittest import mock


class TestPreprocessor:
    def fit(self, *args) -> TestPreprocessor:
        return self

    def transform(self, data: np.ndarray) -> np.ndarray:
        # Remove the last feature as a "preprocessing step".
        return data[:, :-1]


@pytest.mark.parametrize("transformer_cls, transformer_kwargs", [
    (as_transformer(LinearRegression), {}),
    (MinimumConditionalEntropyTransformer, {"frac": 0.01}),
])
def test_infer(simulated_data: np.ndarray, simulated_params: np.ndarray, observed_data: np.ndarray,
               tmp_path: Path, transformer_cls: Type[Transformer],
               transformer_kwargs: Dict[str, Any]) -> None:
    # Set up a dummy configuration.
    config = InferenceConfig(
        0.01,
        transformer_cls,
        transformer_kwargs,
        TestPreprocessor,
    )

    # Create paths and write the data to disk.
    simulated = tmp_path / "simulated.pkl"
    observed = tmp_path / "observed.pkl"
    output = tmp_path / "output.pkl"

    with simulated.open("wb") as fp:
        pickle.dump({
            "data": simulated_data,
            "params": simulated_params,
        }, fp)

    with observed.open("wb") as fp:
        pickle.dump({
            "data": observed_data[:7],
        }, fp)

    with mock.patch.dict(INFERENCE_CONFIGS, test=config):
        __main__(map(str, ["test", simulated, observed, output]))

    with output.open("rb") as fp:
        result = pickle.load(fp)

    # Verify the shape of the sample.
    assert result["samples"].shape == (7, 1000, simulated_params.shape[-1])


@pytest.mark.parametrize("config", [x for x in INFERENCE_CONFIGS if x.startswith("coal")])
def test_infer_coal(config: str, tmp_path: Path) -> None:
    # Split up the data to test and training sets.
    coaloracle = Path(__file__).parent.parent / "data/coaloracle_sample.csv"
    __main__preprocess_coal(map(str, [coaloracle, tmp_path, "simulated:98", "observed:2"]))

    output = tmp_path / "output.pkl"
    argv = [config, tmp_path / "simulated.pkl", tmp_path / "observed.pkl", output]

    # Dump a simple transformer if required.
    transformer_cls = INFERENCE_CONFIGS[config].transformer_cls
    if transformer_cls == "pickled":
        transformer = tmp_path / "transformer.pkl"
        with transformer.open("wb") as fp:
            pickle.dump({
                "transformer": NeuralTransformer(nn.Linear(7, 2)),
            }, fp)
        argv.extend(["--transformer-kwargs", json.dumps({"transformer": str(transformer)})])

    def _run():
        # We need to increase the fraction of samples to estimate the entropy in this test.
        with mock.patch.object(INFERENCE_CONFIGS[config], "frac", 0.1):
            __main__(map(str, argv))

    if isinstance(transformer_cls, Type) and \
            issubclass(transformer_cls, MinimumConditionalEntropyTransformer):
        with mock.patch.object(INFERENCE_CONFIGS[config], "transformer_kwargs", {"frac": 0.1}):
            _run()
    else:
        _run()

    with output.open("rb") as fp:
        result = pickle.load(fp)

    assert result["samples"].shape == (2, 9, 2)
