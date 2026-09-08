"""Connect candidate interventions to the validated paths they sever."""

import hashlib
import json
from collections.abc import Iterable

import numpy as np
from numpy.typing import NDArray

from lumon.model import AttackGraph, InterventionCatalog, PathSet


class StaleMatrixError(Exception):
    """The path set or intervention catalog changed after matrix construction."""


class CoverageMatrix:
    """A positional grid of interventions by validated attack paths."""

    def __init__(
        self,
        path_set: PathSet,
        catalog: InterventionCatalog,
        graph: AttackGraph,
    ) -> None:
        self._validate_edge_references(path_set, catalog, graph)

        self.intervention_ids = [intervention.id for intervention in catalog.interventions]
        self.path_ids = [path.id for path in path_set.paths]
        self.path_weights: NDArray[np.float64] = np.array(
            [path.weight for path in path_set.paths],
            dtype=np.float64,
        )
        self.intervention_costs: NDArray[np.float64] = np.array(
            [intervention.cost.tier.numeric_value for intervention in catalog.interventions],
            dtype=np.float64,
        )

        self._intervention_positions = {
            intervention_id: index for index, intervention_id in enumerate(self.intervention_ids)
        }
        self._path_positions = {path_id: index for index, path_id in enumerate(self.path_ids)}

        path_edge_sets = {path.id: frozenset(path.edge_ids) for path in path_set.paths}
        self._matrix: NDArray[np.bool_] = np.zeros(
            (len(self.intervention_ids), len(self.path_ids)),
            dtype=np.bool_,
        )
        for intervention_index, intervention in enumerate(catalog.interventions):
            for path_index, path_id in enumerate(self.path_ids):
                self._matrix[
                    intervention_index, path_index
                ] = not intervention.removes_edge_ids.isdisjoint(path_edge_sets[path_id])

        self.fingerprint = self._calculate_fingerprint(path_set, catalog)

    def verify_fingerprint(
        self,
        path_set: PathSet,
        catalog: InterventionCatalog,
    ) -> None:
        if self._calculate_fingerprint(path_set, catalog) != self.fingerprint:
            raise StaleMatrixError(
                "coverage matrix no longer matches the supplied path set and "
                "intervention catalog; rebuild it"
            )

    def covers(self, intervention_id: str, path_id: str) -> bool:
        return bool(
            self._matrix[
                self._intervention_positions[intervention_id],
                self._path_positions[path_id],
            ]
        )

    def paths_covered_by(self, intervention_id: str) -> list[str]:
        row = self._matrix[self._intervention_positions[intervention_id]]
        return [path_id for index, path_id in enumerate(self.path_ids) if bool(row[index])]

    def interventions_covering(self, path_id: str) -> list[str]:
        column = self._matrix[:, self._path_positions[path_id]]
        return [
            intervention_id
            for index, intervention_id in enumerate(self.intervention_ids)
            if bool(column[index])
        ]

    def uncoverable_path_ids(self) -> list[str]:
        return [
            path_id
            for index, path_id in enumerate(self.path_ids)
            if not bool(self._matrix[:, index].any())
        ]

    def redundant_intervention_ids(self) -> list[str]:
        return [
            intervention_id
            for index, intervention_id in enumerate(self.intervention_ids)
            if not bool(self._matrix[index].any())
        ]

    def dominated_intervention_ids(self) -> list[str]:
        dominated: list[str] = []

        for candidate_index, candidate_id in enumerate(self.intervention_ids):
            candidate_coverage = self._matrix[candidate_index]
            candidate_cost = float(self.intervention_costs[candidate_index])

            for alternative_index in range(len(self.intervention_ids)):
                if alternative_index == candidate_index:
                    continue

                alternative_coverage = self._matrix[alternative_index]
                alternative_cost = float(self.intervention_costs[alternative_index])
                is_superset = bool(alternative_coverage[candidate_coverage].all())
                is_strictly_better = alternative_cost < candidate_cost or not np.array_equal(
                    alternative_coverage,
                    candidate_coverage,
                )

                if alternative_cost <= candidate_cost and is_superset and is_strictly_better:
                    dominated.append(candidate_id)
                    break

        return dominated

    def weight_covered_by(
        self,
        intervention_ids: Iterable[str],
    ) -> float:
        covered = self._coverage_for(intervention_ids)
        return float(self.path_weights[covered].sum())

    def is_full_cover(self, intervention_ids: Iterable[str]) -> bool:
        return bool(self._coverage_for(intervention_ids).all())

    def to_dense(self) -> NDArray[np.bool_]:
        return self._matrix.copy()

    def __repr__(self) -> str:
        row_count, column_count = self._matrix.shape
        if row_count <= 12 and column_count <= 12:
            values = self._matrix.astype(np.uint8).tolist()
            return (
                "CoverageMatrix("
                f"intervention_ids={self.intervention_ids!r}, "
                f"path_ids={self.path_ids!r}, "
                f"matrix={values!r})"
            )
        return f"CoverageMatrix(shape=({row_count}, {column_count}))"

    def _coverage_for(
        self,
        intervention_ids: Iterable[str],
    ) -> NDArray[np.bool_]:
        covered = np.zeros(len(self.path_ids), dtype=np.bool_)
        for intervention_id in intervention_ids:
            covered |= self._matrix[self._intervention_positions[intervention_id]]
        return covered

    @staticmethod
    def _validate_edge_references(
        path_set: PathSet,
        catalog: InterventionCatalog,
        graph: AttackGraph,
    ) -> None:
        validated_edge_ids = {edge.id for edge in graph.validated_edges()}
        path_edge_ids = {edge_id for path in path_set.paths for edge_id in path.edge_ids}
        intervention_edge_ids = {
            edge_id
            for intervention in catalog.interventions
            for edge_id in intervention.removes_edge_ids
        }

        invalid_path_edge_ids = sorted(path_edge_ids - validated_edge_ids)
        if invalid_path_edge_ids:
            raise ValueError(
                "path set references edges absent from the graph's validated "
                f"edge set: {', '.join(invalid_path_edge_ids)}"
            )

        invalid_intervention_edge_ids = sorted(intervention_edge_ids - validated_edge_ids)
        if invalid_intervention_edge_ids:
            raise ValueError(
                "intervention catalog references edges absent from the graph's "
                f"validated edge set: {', '.join(invalid_intervention_edge_ids)}"
            )

    @staticmethod
    def _calculate_fingerprint(
        path_set: PathSet,
        catalog: InterventionCatalog,
    ) -> str:
        payload = {
            "paths": [
                {
                    "id": path.id,
                    "edge_ids": path.edge_ids,
                    "weight": path.weight,
                }
                for path in path_set.paths
            ],
            "interventions": [
                {
                    "id": intervention.id,
                    "removes_edge_ids": sorted(intervention.removes_edge_ids),
                    "cost": intervention.cost.tier.numeric_value,
                }
                for intervention in catalog.interventions
            ],
        }
        encoded = json.dumps(
            payload,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
