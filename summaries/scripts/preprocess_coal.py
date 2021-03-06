import argparse
import numpy as np
import os
import pandas as pd
import pickle
from .. import util


def __main__(args=None):
    util.setup_script()
    parser = argparse.ArgumentParser()
    parser.add_argument('coaloracle', help='file containing all samples')
    parser.add_argument('directory', help='output directory')
    parser.add_argument('filenames', nargs='+', help='filenames in the format <name>=<size>')
    args = parser.parse_args(args)

    # Load the data and shuffle it (see https://stackoverflow.com/a/34879805/1150961).
    data = pd.read_csv(args.coaloracle).sample(frac=1.0).reset_index(drop=True)

    # Identify the splits and save the data.
    splits = {filename: int(size) for filename, size in map(lambda x: x.split('='), args.filenames)}
    total = sum(splits.values())
    assert total == len(data), f'expected {len(data)} number of samples but got {total}'

    # Different versions of the dataset have different column names. Pick the one appropriate for
    # this dataset. The ordering is correct (cf. Table 1 in Nunes and Balding (2010)).
    data_column_candidates = [
        ['segsites', 'unif', 'meandiff', 'R2', 'nhap', 'fhap', 'shap'],
        [f'C{i}' for i in range(1, 8)],
    ]
    data_columns = None
    for candidate in data_column_candidates:
        if not set(candidate) - set(data.columns):
            data_columns = candidate
    assert len(data_columns) == 7

    offset = 0
    for filename, size in splits.items():
        split: pd.DataFrame = data.iloc[offset:offset + size]
        offset += size
        result = {
            'args': vars(args),
            'filename': filename,
            'samples': {
                'theta': split[['theta', 'rho']].values.astype(np.float32),
                'x': split[data_columns].values.astype(np.float32),
            }
        }

        with util.sopen(os.path.join(args.directory, filename), 'wb') as fp:
            pickle.dump(result, fp)


if __name__ == '__main__':
    __main__()
