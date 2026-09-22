import unittest

from fca import (
    ExchangeCapsule,
    ExchangeEvidence,
    ExchangeRegistry,
    ExchangeState,
    RepositoryEvidenceImporter,
)


FAP_V87_71_COMMIT = "67538f84e33cfc8aa2dae4cba42857bdb33b3e8c"


def capsule_raw():
    return {
        "schema": "fca-fap.exchange.v1",
        "source_project": "FAP",
        "source_commit": FAP_V87_71_COMMIT,
        "capability": "repository_coding_verified_candidate",
        "mechanism": {
            "contract": "fap.repository.coding.v1",
            "plan_contract": "fap.repository.plan.v1",
            "verification_contract": "fap.repository.verification.v1",
            "plan_id": "1" * 64,
            "repository_digest": "2" * 64,
            "goal_sha256": "3" * 64,
            "files": [
                {
                    "path": "calc.py",
                    "operation": "modify",
                    "before_sha256": "4" * 64,
                    "after_sha256": "5" * 64,
                }
            ],
            "provider_boundary": "declarative_file_edits_only",
            "control_pattern": "reader_planner_executor_verifier_bounded_repair",
        },
        "evidence": {
            "status": "verified_candidate",
            "repair_contract": "fap.repository.repair.v1",
            "attempt_count": 1,
            "repairs_used": 0,
            "final_execution_state": "applied_in_sandbox",
            "final_verification_state": "verified_candidate",
            "static_passed": True,
            "commands": [
                {
                    "name": "python_static_compile",
                    "phase": "static",
                    "passed": True,
                    "returncode": 0,
                    "timed_out": False,
                    "output_limited": False,
                },
                {
                    "name": "focused",
                    "phase": "focused",
                    "passed": True,
                    "returncode": 0,
                    "timed_out": False,
                    "output_limited": False,
                },
                {
                    "name": "regression",
                    "phase": "regression",
                    "passed": True,
                    "returncode": 0,
                    "timed_out": False,
                    "output_limited": False,
                },
            ],
        },
        "constraints": [
            "Provenance only: this capsule contains no source code, replacement text, excerpts, diffs, or command output.",
            "FCA must not execute or activate code from this capsule.",
            "FCA connectome selection and reward-plasticity controller remain authoritative.",
            "Independent FCA evidence is required before exchange acceptance or any capability adaptation.",
            "No automatic branch promotion, push, pull request, merge, or main update is authorized by this capsule.",
        ],
    }


def capsule_from(raw):
    return ExchangeCapsule.from_dict(ExchangeCapsule.seal(raw))


class RepositoryExchangeTests(unittest.TestCase):
    def test_valid_fap_repository_evidence_is_inert_and_parses(self):
        cap = capsule_from(capsule_raw())
        parsed = RepositoryEvidenceImporter().validate(cap)

        self.assertEqual(parsed.source_commit, FAP_V87_71_COMMIT)
        self.assertEqual(parsed.plan_id, "1" * 64)
        self.assertEqual(parsed.repository_digest, "2" * 64)
        self.assertEqual(parsed.goal_sha256, "3" * 64)
        self.assertEqual(len(parsed.files), 1)
        self.assertEqual(parsed.files[0].path, "calc.py")
        self.assertEqual(parsed.files[0].operation, "modify")
        self.assertEqual(parsed.attempt_count, 1)
        self.assertEqual(parsed.repairs_used, 0)
        self.assertTrue(parsed.static_passed)

    def test_receive_never_auto_promotes_without_independent_evidence(self):
        cap = capsule_from(capsule_raw())
        registry = ExchangeRegistry(shadow_after=1, accept_after=2)
        importer = RepositoryEvidenceImporter()

        first = importer.receive(cap, registry)
        second = importer.receive(cap, registry)
        self.assertEqual(first.state, ExchangeState.RECEIVED)
        self.assertEqual(second.state, ExchangeState.RECEIVED)
        self.assertEqual(registry.accepted_capabilities(), ())

        self.assertEqual(
            registry.add_evidence(
                cap.digest,
                ExchangeEvidence("independent-1", True, quality_delta=0.0),
            ),
            ExchangeState.SHADOW,
        )
        self.assertEqual(
            importer.receive(cap, registry).state,
            ExchangeState.SHADOW,
        )
        self.assertEqual(
            registry.add_evidence(
                cap.digest,
                ExchangeEvidence("independent-2", True, quality_delta=0.0),
            ),
            ExchangeState.ACCEPTED,
        )
        self.assertEqual(
            registry.accepted_capabilities(),
            ("repository_coding_verified_candidate",),
        )

    def test_source_or_executable_payload_keys_are_rejected(self):
        raw = capsule_raw()
        raw["mechanism"]["content"] = "print('must not cross project')"
        cap = capsule_from(raw)

        with self.assertRaisesRegex(ValueError, "executable/source"):
            RepositoryEvidenceImporter().validate(cap)

    def test_unsafe_repository_path_is_rejected(self):
        raw = capsule_raw()
        raw["mechanism"]["files"][0]["path"] = "../escape.py"
        cap = capsule_from(raw)

        with self.assertRaisesRegex(ValueError, "unsafe"):
            RepositoryEvidenceImporter().validate(cap)

    def test_failed_or_bounded_out_verification_is_rejected(self):
        raw = capsule_raw()
        raw["evidence"]["commands"][1]["passed"] = False
        cap = capsule_from(raw)

        with self.assertRaisesRegex(ValueError, "must pass"):
            RepositoryEvidenceImporter().validate(cap)

        raw = capsule_raw()
        raw["evidence"]["commands"][1]["output_limited"] = True
        cap = capsule_from(raw)
        with self.assertRaisesRegex(ValueError, "output-limited"):
            RepositoryEvidenceImporter().validate(cap)

    def test_connectome_and_independent_evidence_constraints_are_required(self):
        raw = capsule_raw()
        raw["constraints"] = [
            "FCA must not execute or activate code from this capsule.",
        ]
        cap = capsule_from(raw)

        with self.assertRaisesRegex(ValueError, "constraints are incomplete"):
            RepositoryEvidenceImporter().validate(cap)

    def test_successful_candidate_branch_provenance_is_inert_metadata(self):
        raw = capsule_raw()
        raw["evidence"]["promotion"] = {
            "state": "candidate_branch_created",
            "branch": "fap/candidate/1234567890abcdef",
            "commit_sha": "6" * 40,
            "base_commit": "7" * 40,
        }
        cap = capsule_from(raw)
        parsed = RepositoryEvidenceImporter().validate(cap)

        self.assertEqual(
            parsed.promotion_branch,
            "fap/candidate/1234567890abcdef",
        )
        self.assertEqual(parsed.promotion_commit, "6" * 40)


if __name__ == "__main__":
    unittest.main()
