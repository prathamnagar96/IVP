"""Spatial block cross-validation and spatial leakage test (Section 5.4, 9).

Ensures that training and evaluation folds are separated into spatial blocks
larger than the spatial-autocorrelation range (e.g. 10 km), preventing optimistic leakage.
"""

from typing import List, Tuple, Dict, Any, Generator, Optional
import numpy as np


class SpatialBlockCV:
    def __init__(
        self,
        block_size_m: float = 10000.0,
        n_splits: int = 5,
        random_state: int = 42,
    ):
        self.block_size_m = block_size_m
        self.n_splits = n_splits
        self.random_state = random_state

    def assign_blocks(self, coords: np.ndarray) -> np.ndarray:
        """Assign 2D coordinates (x, y) in metric CRS to discrete spatial block grid IDs."""
        x = coords[:, 0]
        y = coords[:, 1]
        x_idx = np.floor(x / self.block_size_m).astype(np.int64)
        y_idx = np.floor(y / self.block_size_m).astype(np.int64)

        # Unique block identifiers
        block_ids = np.array([f"{xi}_{yi}" for xi, yi in zip(x_idx, y_idx)])
        return block_ids

    def split(
        self, X: np.ndarray, y: Optional[np.ndarray] = None, coords: Optional[np.ndarray] = None
    ) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        """Yield (train_indices, test_indices) partitioned strictly by spatial blocks."""
        n_samples = len(X)
        if coords is None:
            raise ValueError("Metric spatial coordinates (coords) are required for SpatialBlockCV.")

        block_ids = self.assign_blocks(coords)
        unique_blocks = np.unique(block_ids)

        rng = np.random.RandomState(self.random_state)
        shuffled_blocks = rng.permutation(unique_blocks)

        # Distribute blocks evenly among folds
        fold_blocks = np.array_split(shuffled_blocks, self.n_splits)

        indices = np.arange(n_samples)
        for fold_idx in range(self.n_splits):
            test_blocks = set(fold_blocks[fold_idx])
            test_mask = np.isin(block_ids, list(test_blocks))
            test_idx = indices[test_mask]
            train_idx = indices[~test_mask]

            if len(test_idx) == 0:
                continue

            yield train_idx, test_idx


def verify_no_spatial_leakage(
    train_indices: np.ndarray,
    test_indices: np.ndarray,
    unit_ids: List[str],
) -> bool:
    """Invariant test: verify no slope unit ID exists in both train and test sets."""
    train_set = set(np.array(unit_ids)[train_indices])
    test_set = set(np.array(unit_ids)[test_indices])

    intersection = train_set.intersection(test_set)
    if len(intersection) > 0:
        raise AssertionError(
            f"Spatial leakage detected! {len(intersection)} units present in both train and test: {list(intersection)[:5]}"
        )
    return True
