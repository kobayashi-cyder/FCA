"""FCA — Fly Connectome Agent."""

from .agent import FCAAgent, Decision
from .autonomy import AutonomousLoop, GoalReport, Step
from .canary import CanaryObservation, StagedCanary
from .code_generation import CodeGenerationError, CodeGenerationResult, FCACodeGenerator, ProgramIR
from .capability import CapabilityPriorityEngine, GapEvidence, GapKind
from .concepts import ConceptGraph, Fact
from .exchange import ExchangeCapsule
from .exchange_registry import ExchangeEvidence, ExchangeRegistry, ExchangeState
from .goal_contract import CriterionAssessment, GoalAssessment, GoalContract, GoalCritic
from .hot_path import HotPathStatus, VerifiedHotPath
from .hypothesis import Hypothesis, HypothesisCompetition, HypothesisEngine
from .importers import edge_csv_to_manifest, flywire_codex_files_to_manifest
from .improvement import CandidateLifecycle, CandidateState, Evidence, FailureMemory, FailureRecord
from .lazy_organs import LazyOrganRegistry, LazyOrganSpec
from .memory import HotColdMemory, MemoryItem
from .organs import OrganRegistry, OrganResult
from .provider_gate import ProviderHealth, ProviderHealthGate
from .provenance import ProvenanceChain, ProvenanceEvent
from .rebuilt_runtime import (
    FCARebuiltRuntime,
    IntegrityVerifier,
    RuntimeStep,
    VerificationIssue,
    VerificationResult,
)
from .repository_ast_patch import (
    ASTFunctionPatchGenerator,
    ASTFunctionPatchResult,
    ASTPatchError,
)
from .repository_generation import (
    FCARepositoryGenerator,
    RepositoryEditCandidate,
    RepositoryGenerationError,
    RepositoryGenerationResult,
)
from .repository_exchange import (
    RepositoryCodingEvidence,
    RepositoryEvidenceImporter,
    RepositoryExchangeReceipt,
    RepositoryFileEvidence,
)
from .repository_organ import (
    RepositoryCodingHostBinding,
    RepositoryCodingHostResult,
    RepositoryCodingOrgan,
    register_repository_coding_organ,
)
from .repository_host_adapter import (
    FAP_REPOSITORY_HOST_CONTRACT,
    RepositoryHostContractError,
    adapt_fap_repository_host,
    repository_host_runner_from_mapping,
)
from .repository_sandbox import (
    FCASandboxRepairRunner,
    SandboxAttempt,
    SandboxCommand,
    SandboxCommandResult,
    SandboxRepairResult,
)
from .scheduler import OrganBid, ValueScheduler
from .state_store import JSONGoalCheckpointStore
from .structural_controller import StructuralCandidateController, StructuralCandidateEvaluation, StructuralMeasurement
from .structural_coordinator import StructuralImprovementCoordinator, StructuralImprovementOutcome
from .structural_canary import StructuralCanaryController, StructuralCanaryMeasurement, StructuralCanaryStep
from .structural_candidate import (
    StructuralCandidateFactory,
    StructuralCandidateProposal,
    StructuralCandidateRequest,
    StructuralCandidateRun,
    StructuralGenerationResult,
)
from .structural_gate import StructuralEvidence, StructuralImprovementGate
from .teacher_priors import (
    FAPV78CircuitPriors,
    TeacherActivation,
    TeacherAwareFCAAgent,
    TeacherCircuit,
    TeacherPriorError,
)
from .wiring_analysis import WiringComparison, WiringStats, compare_manifest_wiring, manifest_wiring_stats
from .wiring_benchmark import WiringBenchmark, WiringBenchmarkComparison, benchmark_manifest_runtime, compare_wiring_benchmarks
from .wiring_manifest import ConnectomeManifest, WiringUnit
from .world_model import Entity, Relation, WorldGraph

__all__ = [
    "FCAAgent", "Decision", "CanaryObservation", "StagedCanary",
    "CodeGenerationError", "CodeGenerationResult", "FCACodeGenerator", "ProgramIR",
    "CapabilityPriorityEngine", "GapEvidence", "GapKind",
    "ConceptGraph", "Fact", "ExchangeCapsule", "ExchangeEvidence", "ExchangeRegistry", "ExchangeState",
    "GoalContract", "CriterionAssessment", "GoalAssessment", "GoalCritic",
    "HotPathStatus", "VerifiedHotPath",
    "Hypothesis", "HypothesisCompetition", "HypothesisEngine",
    "edge_csv_to_manifest", "flywire_codex_files_to_manifest", "AutonomousLoop", "GoalReport", "Step",
    "OrganRegistry", "OrganResult", "LazyOrganRegistry", "LazyOrganSpec",
    "ProviderHealth", "ProviderHealthGate", "ProvenanceChain", "ProvenanceEvent",
    "CandidateLifecycle", "CandidateState", "Evidence", "FailureMemory", "FailureRecord",
    "HotColdMemory", "MemoryItem", "OrganBid", "ValueScheduler",
    "JSONGoalCheckpointStore", "ConnectomeManifest", "WiringUnit",
    "WiringComparison", "WiringStats", "compare_manifest_wiring", "manifest_wiring_stats",
    "WiringBenchmark", "WiringBenchmarkComparison", "benchmark_manifest_runtime", "compare_wiring_benchmarks",
    "StructuralEvidence", "StructuralImprovementGate",
    "StructuralCandidateController", "StructuralCandidateEvaluation", "StructuralMeasurement",
    "StructuralImprovementCoordinator", "StructuralImprovementOutcome",
    "StructuralCanaryController", "StructuralCanaryMeasurement", "StructuralCanaryStep",
    "StructuralCandidateFactory", "StructuralCandidateProposal", "StructuralCandidateRequest",
    "StructuralCandidateRun", "StructuralGenerationResult",
    "FAPV78CircuitPriors", "TeacherActivation", "TeacherAwareFCAAgent",
    "TeacherCircuit", "TeacherPriorError",
    "FCARebuiltRuntime", "IntegrityVerifier", "RuntimeStep",
    "VerificationIssue", "VerificationResult",
    "ASTFunctionPatchGenerator", "ASTFunctionPatchResult", "ASTPatchError",
    "FCARepositoryGenerator", "RepositoryEditCandidate",
    "RepositoryGenerationError", "RepositoryGenerationResult",
    "RepositoryCodingEvidence", "RepositoryEvidenceImporter",
    "RepositoryExchangeReceipt", "RepositoryFileEvidence",
    "RepositoryCodingHostBinding", "RepositoryCodingHostResult",
    "RepositoryCodingOrgan", "register_repository_coding_organ",
    "FAP_REPOSITORY_HOST_CONTRACT", "RepositoryHostContractError",
    "FCASandboxRepairRunner", "SandboxAttempt", "SandboxCommand",
    "SandboxCommandResult", "SandboxRepairResult",
    "adapt_fap_repository_host", "repository_host_runner_from_mapping",
    "Entity", "Relation", "WorldGraph",
]
