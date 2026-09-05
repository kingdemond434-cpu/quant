"""Alpha Recombination Engine — breaks strategies into atomic pieces and recombines orthogonally.

Atomic pieces:
- trigger / entry condition
- regime filter
- information source
- entry method
- exit method
- execution mode
- participant constraint
- holding horizon
- stop/trail logic
- session filter

Recombines ONLY orthogonal atoms (low mutual information) to generate
economically different hypotheses from existing pieces.
"""

from __future__ import annotations

import hashlib
import json
import itertools
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd


@dataclass
class AlphaAtom:
    """One atomic piece of a strategy."""
    atom_type: str                              # trigger, regime, info_source, entry, exit, execution, participant, horizon, stop, session
    value: str                                  # e.g., "session_breakout", "london_am", "warehouse_receipts", "stop_order", "vol_scaled"
    source_strategy: str                        # original strategy ID
    economic_meaning: str                       # what this piece represents
    mutual_info: dict[str, float] = field(default_factory=dict)  # MI with other atoms
    
    # Statistics
    historical_edge_bps: float = 0.0            # edge when this atom was present
    frequency: float = 0.0                      # how often this atom appears
    orthogonality_score: float = 1.0            # 0-1, higher = more independent


@dataclass
class RecombinantHypothesis:
    """A hypothesis created by recombining atoms."""
    id: str
    atoms: list[AlphaAtom]
    mechanism_class: str
    expected_orthogonality: float               # average pairwise orthogonality
    estimated_edge_bps: float
    source_strategies: list[str]                # which original strategies contributed
    recombination_type: str                     # "orthogonal", "complementary", "contrarian"
    falsifier: str
    metadata: dict = field(default_factory=dict)


class AtomLibrary:
    """Library of extracted alpha atoms from all strategies."""
    
    def __init__(self):
        self.atoms: dict[str, list[AlphaAtom]] = {}  # atom_type -> list of atoms
        self.atom_index: dict[str, AlphaAtom] = {}    # atom_id -> atom
        self.strategy_atoms: dict[str, list[str]] = {}  # strategy_id -> list of atom_ids
    
    def extract_atoms_from_strategy(self, strategy_spec: dict) -> list[AlphaAtom]:
        """Decompose a strategy into atomic pieces."""
        atoms = []
        strategy_id = strategy_spec.get("id", "unknown")
        
        # Trigger / Entry
        trigger = strategy_spec.get("trigger", strategy_spec.get("entry_condition", ""))
        if trigger:
            atoms.append(AlphaAtom(
                atom_type="trigger",
                value=trigger,
                source_strategy=strategy_id,
                economic_meaning=f"Entry trigger: {trigger}",
            ))
        
        # Regime filter
        regime = strategy_spec.get("regime", strategy_spec.get("regime_filter", "all"))
        atoms.append(AlphaAtom(
            atom_type="regime",
            value=regime,
            source_strategy=strategy_id,
            economic_meaning=f"Regime filter: {regime}",
        ))
        
        # Information source
        info_source = strategy_spec.get("information_source", strategy_spec.get("source", "price"))
        atoms.append(AlphaAtom(
            atom_type="info_source",
            value=info_source,
            source_strategy=strategy_id,
            economic_meaning=f"Information source: {info_source}",
        ))
        
        # Entry method
        entry_method = strategy_spec.get("entry_method", "stop_order")
        atoms.append(AlphaAtom(
            atom_type="entry",
            value=entry_method,
            source_strategy=strategy_id,
            economic_meaning=f"Entry method: {entry_method}",
        ))
        
        # Exit method
        exit_method = strategy_spec.get("exit", strategy_spec.get("exit_method", "tp_sl"))
        atoms.append(AlphaAtom(
            atom_type="exit",
            value=exit_method,
            source_strategy=strategy_id,
            economic_meaning=f"Exit method: {exit_method}",
        ))
        
        # Execution mode
        execution = strategy_spec.get("execution", "market")
        atoms.append(AlphaAtom(
            atom_type="execution",
            value=execution,
            source_strategy=strategy_id,
            economic_meaning=f"Execution mode: {execution}",
        ))
        
        # Participant constraint
        participant = strategy_spec.get("participant", strategy_spec.get("forced_participant", "none"))
        atoms.append(AlphaAtom(
            atom_type="participant",
            value=participant,
            source_strategy=strategy_id,
            economic_meaning=f"Forced participant: {participant}",
        ))
        
        # Holding horizon
        horizon = strategy_spec.get("horizon", strategy_spec.get("holding_horizon", "intraday"))
        atoms.append(AlphaAtom(
            atom_type="horizon",
            value=horizon,
            source_strategy=strategy_id,
            economic_meaning=f"Holding horizon: {horizon}",
        ))
        
        # Stop/Trail logic
        stop = strategy_spec.get("stop", strategy_spec.get("stop_loss", "atr"))
        atoms.append(AlphaAtom(
            atom_type="stop",
            value=stop,
            source_strategy=strategy_id,
            economic_meaning=f"Stop logic: {stop}",
        ))
        
        # Session filter
        session = strategy_spec.get("session", strategy_spec.get("window", "all"))
        atoms.append(AlphaAtom(
            atom_type="session",
            value=session,
            source_strategy=strategy_id,
            economic_meaning=f"Session filter: {session}",
        ))
        
        # Register atoms
        for atom in atoms:
            atom_id = f"{atom.atom_type}:{atom.value}:{strategy_id}"
            self.atom_index[atom_id] = atom
            if atom.atom_type not in self.atoms:
                self.atoms[atom.atom_type] = []
            self.atoms[atom.atom_type].append(atom)
        
        self.strategy_atoms[strategy_id] = [f"{a.atom_type}:{a.value}:{strategy_id}" for a in atoms]
        
        return atoms
    
    def compute_mutual_information(self, returns_data: dict[str, pd.Series]) -> None:
        """Compute mutual information between atoms based on co-occurrence in profitable strategies."""
        # Simplified: compute correlation of atom presence with strategy performance
        for atom_type, atoms in self.atoms.items():
            for atom in atoms:
                # This would be computed from historical data
                # For now, set defaults based on atom type
                if atom_type in ["trigger", "info_source", "participant"]:
                    atom.orthogonality_score = 0.8  # These tend to be more independent
                elif atom_type in ["entry", "exit", "execution"]:
                    atom.orthogonality_score = 0.6  # Some overlap
                elif atom_type in ["regime", "session", "horizon"]:
                    atom.orthogonality_score = 0.5  # More correlated
                else:
                    atom.orthogonality_score = 0.7
    
    def get_atoms_by_type(self, atom_type: str) -> list[AlphaAtom]:
        return self.atoms.get(atom_type, [])
    
    def get_orthogonal_pairs(self, threshold: float = 0.3) -> list[tuple[str, str, float]]:
        """Find pairs of atoms with low mutual information (high orthogonality)."""
        pairs = []
        atom_list = list(self.atom_index.values())
        
        for i, a1 in enumerate(atom_list):
            for a2 in atom_list[i+1:]:
                # Simplified MI: assume atoms of different types are more orthogonal
                if a1.atom_type != a2.atom_type:
                    mi = 0.1  # Low MI for different types
                else:
                    # Same type - higher MI
                    mi = 0.5 if a1.value != a2.value else 1.0
                
                if mi < threshold:
                    pairs.append((a1.atom_type + ":" + a1.value, a2.atom_type + ":" + a2.value, mi))
        
        return pairs


class RecombinationEngine:
    """Generates new hypotheses by recombining orthogonal atoms."""
    
    def __init__(self, atom_library: AtomLibrary):
        self.library = atom_library
        self.recombinants: list[RecombinantHypothesis] = []
    
    def generate_orthogonal_recombinants(self, 
                                          max_atoms: int = 5,
                                          min_orthogonality: float = 0.6,
                                          max_combinations: int = 100) -> list[RecombinantHypothesis]:
        """Generate hypotheses by combining orthogonal atoms."""
        recombinants = []
        
        # Get all atom types
        atom_types = list(self.library.atoms.keys())
        
        # Strategy 1: Complementary atoms (different types that naturally combine)
        complementary_groups = {
            "flow": ["trigger", "participant", "info_source", "horizon"],
            "execution": ["entry", "execution", "stop", "horizon"],
            "regime": ["regime", "trigger", "session", "horizon"],
            "relative_value": ["info_source", "trigger", "exit", "horizon"],
        }
        
        for group_name, atom_types in complementary_groups.items():
            # Pick one atom from each type
            recombinants.extend(self._recombine_group(group_name, atom_types, max_per_group=20))
        
        # Strategy 2: Orthogonal substitution (replace one atom in proven strategy)
        # This would substitute atoms in proven strategies with orthogonal alternatives
        
        # Strategy 3: Contrarian recombination (invert a proven atom)
        # e.g., if "stop_order" works, try "limit_order" with same other atoms
        
        # Filter by orthogonality
        filtered = [r for r in recombinants if r.expected_orthogonality >= min_orthogonality]
        
        # Sort by estimated edge
        filtered.sort(key=lambda r: -r.estimated_edge_bps)
        
        self.recombinants = filtered[:max_combinations]
        return filtered
    
    def _recombine_group(self, group_name: str, atom_types: list[str], max_per_group: int) -> list[RecombinantHypothesis]:
        """Generate recombinations from a group of complementary atom types."""
        recombinants = []
        
        # Get available atoms for each type
        available = {}
        for atype in atom_types:
            atoms = self.library.get_atoms_by_type(atype)
            if atoms:
                available[atype] = atoms
        
        if len(available) < 2:
            return []
        
        # Generate combinations (one from each type)
        atom_lists = [available[at] for at in atom_types if at in available]
        
        count = 0
        for combo in itertools.product(*atom_lists):
            if count >= 20:
                break
            
            # Check orthogonality
            ortho = self._compute_group_orthogonality(combo)
            
            if ortho >= 0.5:  # Minimum orthogonality
                atoms = list(combo)
                
                # Determine mechanism class
                mech_class = self._infer_mechanism_class(combo)
                
                # Estimate edge (simplified heuristic)
                edge_bps = self._estimate_edge_bps(combo)
                
                # Generate falsifier
                falsifier = self._generate_falsifier(combo)
                
                recomb = RecombinantHypothesis(
                    id=f"REC-{datetime.now(UTC).strftime('%Y%m%d')}-{hashlib.md5(str([a.value for a in combo]).encode()).hexdigest()[:6]}",
                    atoms=atoms,
                    mechanism_class=mech_class,
                    expected_orthogonality=self._compute_group_orthogonality(combo),
                    estimated_edge_bps=edge_bps,
                    source_strategies=list(set(a.source_strategy for a in atoms)),
                    recombination_type="orthogonal",
                    falsifier=falsifier,
                    metadata={
                        "group": group_name,
                        "atom_types": [a.atom_type for a in atoms],
                    }
                )
                recombinants.append(recomb)
                count += 1
        
        return recombinants
    
    def _compute_group_orthogonality(self, atoms: tuple) -> float:
        """Compute average pairwise orthogonality in a group."""
        if len(atoms) < 2:
            return 1.0
        
        orthos = []
        for i, a1 in enumerate(atoms):
            for a2 in atoms[i+1:]:
                # Different types = more orthogonal
                if a1.atom_type != a2.atom_type:
                    orthos.append(0.8)
                else:
                    # Same type - check if different values
                    if a1.value != a2.value:
                        orthos.append(0.6)
                    else:
                        orthos.append(0.0)  # Same atom
        
        return np.mean(orthos) if orthos else 1.0
    
    def _infer_mechanism_class(self, atoms: tuple) -> str:
        """Infer mechanism class from atom combination."""
        types = {a.atom_type for a in atoms}
        values = {a.value for a in atoms}
        
        # Heuristics
        if "participant" in {a.atom_type for a in atoms}:
            participant_values = {a.value for a in atoms if a.atom_type == "participant"}
            if any("hedge" in v or "AP" in v or "pension" in v for v in participant_values):
                return "forced_flow"
            if any("dealer" in v or "gamma" in v for v in participant_values):
                return "information_shock"
        
        if "info_source" in {a.atom_type for a in atoms}:
            info_values = {a.value for a in atoms if a.atom_type == "info_source"}
            if any("warehouse" in v or "inventory" in v for v in info_values):
                return "inventory_imbalance"
            if any("news" in v or "event" in v or "trump" in v for v in info_values):
                return "information_shock"
            if any("revision" in v or "macro" in v for v in info_values):
                return "slow_diffusion"
        
        if "trigger" in {a.atom_type for a in atoms}:
            trigger_values = {a.value for a in atoms if a.atom_type == "trigger"}
            if any("breakout" in v or "range" in v for v in trigger_values):
                return "information_shock"
            if any("reversion" in v or "mean" in v for v in trigger_values):
                return "inventory_imbalance"
        
        return "relative_value"
    
    def _estimate_edge_bps(self, atoms: tuple) -> float:
        """Heuristic edge estimation from atom combination."""
        base = 3.0  # bps base
        
        # Bonus for orthogonal types
        types = {a.atom_type for a in atoms}
        base += len(types) * 1.5
        
        # Bonus for specific high-value atoms
        high_value = {
            "participant": 3.0,
            "info_source": 2.0,
            "trigger": 2.0,
            "regime": 1.5,
            "execution": 1.0,
        }
        
        for a in atoms:
            base += high_value.get(a.atom_type, 0.5)
        
        # Bonus for orthogonal combinations
        return min(base, 20.0)  # Cap at 20 bps
    
    def _generate_falsifier(self, atoms: tuple) -> str:
        """Generate falsifier condition for recombinant."""
        conditions = []
        for a in atoms:
            if a.atom_type == "trigger":
                conditions.append(f"trigger {a.value} loses predictive power")
            elif a.atom_type == "info_source":
                conditions.append(f"information source {a.value} becomes public")
            elif a.atom_type == "participant":
                conditions.append(f"participant {a.value} constraint changes")
            elif a.atom_type == "regime":
                conditions.append(f"regime {a.value} disappears")
        
        return " OR ".join(conditions) if conditions else "edge disappears in forward test"


class StrategyDecomposer:
    """Decomposes existing strategies (survivors, near-survivors, public, failed) into atoms."""
    
    def __init__(self, atom_library: AtomLibrary):
        self.library = atom_library
    
    def decompose_survivors(self, survivors_path: Path) -> int:
        """Decompose universal gate survivors."""
        if not survivors_path.exists():
            return 0
        
        with open(survivors_path, "r") as f:
            data = json.load(f)
        
        count = 0
        for key, cert in data.get("survivors", {}).items():
            spec = cert.get("shadow_spec", {})
            spec["id"] = key
            spec["source"] = "universal_survivor"
            
            atoms = self.library.extract_atoms_from_strategy(spec)
            if atoms:
                count += 1
        
        return count
    
    def decompose_near_survivors(self, near_survivors_path: Path) -> int:
        """Decompose near-survivors (failed 1-2 gates)."""
        if not near_survivors_path.exists():
            return 0
        
        # Would load near-survivor data
        return 0
    
    def decompose_public_strategies(self, public_path: Path) -> int:
        """Decompose public strategies (GitHub, MQL5, TradingView, etc.)."""
        # Would load from public strategy database
        return 0
    
    def decompose_failed_strategies(self, failed_path: Path) -> int:
        """Decompose failed strategies for inversion."""
        # Would load from graveyard
        return 0
    
    def decompose_leaderboard_strategies(self, leaderboard_path: Path) -> int:
        """Decompose copy-trader leaderboard strategies."""
        # Would load from leaderboard data
        return 0


def build_full_atom_library(base_path: Path) -> AtomLibrary:
    """Build complete atom library from all available sources."""
    library = AtomLibrary()
    decomposer = StrategyDecomposer(library)
    
    # Decompose universal survivors
    survivors_path = base_path / "desks" / "mt5" / "reports" / "UNIVERSAL_SURVIVORS.json"
    n1 = decomposer.decompose_survivors(survivors_path)
    print(f"Decomposed {n1} universal survivors")
    
    # Decompose QQUANT survivors
    qquant_path = base_path / "desks" / "mt5" / "reports" / "QQUANT_GATES.json"
    n2 = 0  # Would decompose
    print(f"Decomposed {n2} QQUANT survivors")
    
    # Compute mutual information
    library.compute_mutual_information({})
    
    print(f"Total atoms: {sum(len(v) for v in library.atoms.values())}")
    for atype, atoms in library.atoms.items():
        print(f"  {atype}: {len(atoms)} atoms")
    
    return library


def run_recombination_pipeline(base_path: Path) -> list[RecombinantHypothesis]:
    """Run full recombination pipeline."""
    print("Building atom library...")
    library = build_full_atom_library(base_path)
    
    print("\nGenerating recombinants...")
    engine = RecombinationEngine(library)
    recombinants = engine.generate_orthogonal_recombinants(
        max_atoms=5,
        min_orthogonality=0.6,
        max_combinations=100,
    )
    
    print(f"\nGenerated {len(recombinants)} recombinant hypotheses")
    
    # Save recombinants
    output_dir = base_path / "desks" / "mt5" / "data" / "intelligence" / "recombinants"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for r in recombinants:
        out_file = output_dir / f"{r.id}.json"
        with open(out_file, "w") as f:
            json.dump({
                "id": r.id,
                "atoms": [{"type": a.atom_type, "value": a.value, "source": a.source_strategy} for a in r.atoms],
                "mechanism_class": r.mechanism_class,
                "expected_orthogonality": r.expected_orthogonality,
                "estimated_edge_bps": r.estimated_edge_bps,
                "source_strategies": r.source_strategies,
                "recombination_type": r.recombination_type,
                "falsifier": r.falsifier,
                "metadata": r.metadata,
            }, f, indent=2)
    
    print(f"Saved {len(recombinants)} recombinants to {output_dir}")
    
    return recombinants


if __name__ == "__main__":
    base = Path("/home/quant/quant-platform")
    recombinants = run_recombination_pipeline(base)
    
    for r in recombinants[:10]:
        print(f"\n{r.id}:")
        print(f"  Mechanism: {r.mechanism_class}")
        print(f"  Orthogonality: {r.expected_orthogonality:.2f}")
        print(f"  Edge: {r.estimated_edge_bps:.1f} bps")
        print(f"  Sources: {r.source_strategies}")
        print(f"  Falsifier: {r.falsifier}")
        for a in r.atoms:
            print(f"    {a.atom_type}: {a.value} (from {a.source_strategy})")