import unittest

from fca.skill_factory import DeclarativeSkill, SafeBinding, SkillNode, VerifiedSkillComposer


class VerifiedSkillComposerTests(unittest.TestCase):
    def eligible(self, binding_id, fn):
        return SafeBinding(binding_id, fn, verified=True, deterministic=True, side_effect_free=True)

    def test_executes_verified_declarative_dag(self):
        composer = VerifiedSkillComposer((self.eligible("inc", lambda x: x + 1), self.eligible("double", lambda x: x * 2)))
        skill = DeclarativeSkill("inc-double", (SkillNode("a", "inc"), SkillNode("b", "double", ("a",))), "b")
        self.assertEqual(composer.execute(skill, 3), 8)
        self.assertEqual(skill.skill_id, skill.skill_id)

    def test_unverified_binding_fails_closed(self):
        composer = VerifiedSkillComposer((SafeBinding("unsafe", lambda x: x, deterministic=True, side_effect_free=True),))
        skill = DeclarativeSkill("unsafe", (SkillNode("a", "unsafe"),), "a")
        with self.assertRaisesRegex(ValueError, "ineligible binding"):
            composer.execute(skill, 1)

    def test_cycle_is_rejected(self):
        composer = VerifiedSkillComposer((self.eligible("id", lambda x: x),))
        skill = DeclarativeSkill("cycle", (SkillNode("a", "id", ("b",)), SkillNode("b", "id", ("a",))), "a")
        with self.assertRaisesRegex(ValueError, "cycle"):
            composer.validate(skill)

    def test_dead_node_is_rejected(self):
        composer = VerifiedSkillComposer((self.eligible("id", lambda x: x),))
        skill = DeclarativeSkill("dead", (SkillNode("a", "id"), SkillNode("unused", "id")), "a")
        with self.assertRaisesRegex(ValueError, "dead node"):
            composer.validate(skill)

    def test_node_bound_is_fail_closed(self):
        composer = VerifiedSkillComposer((self.eligible("id", lambda x: x),), max_nodes=12)
        nodes = tuple(SkillNode(str(i), "id", (() if i == 0 else (str(i - 1),))) for i in range(13))
        with self.assertRaisesRegex(ValueError, "node bound"):
            composer.validate(DeclarativeSkill("too-large", nodes, "12"))

    def test_composer_has_no_connectome_dependency(self):
        composer = VerifiedSkillComposer((self.eligible("id", lambda x: x),))
        self.assertFalse(hasattr(composer, "connectome"))


if __name__ == "__main__":
    unittest.main()
