"""Fast, dependency-free WGSL contract checks."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..schemas.artifact import ShaderArtifact
from ..schemas.math_spec import MathSpec


@dataclass(frozen=True)
class StaticIssue:
    code: str
    message: str
    severity: str = "error"
    line: int | None = None


def _line_for(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


class WGSLStaticAnalyzer:
    def analyze(
        self, artifact: ShaderArtifact, math_spec: MathSpec | None = None
    ) -> list[StaticIssue]:
        source = artifact.wgsl_code
        issues: list[StaticIssue] = []

        if source.count("{") != source.count("}"):
            issues.append(StaticIssue("unbalanced-braces", "WGSL braces are unbalanced"))
        if "@compute" not in source:
            issues.append(StaticIssue("missing-compute", "missing @compute declaration"))
        entry_match = re.search(rf"\bfn\s+{re.escape(artifact.entry_point)}\b", source)
        if entry_match is None:
            issues.append(
                StaticIssue(
                    "missing-entry-point",
                    f"entry point {artifact.entry_point!r} is not declared",
                )
            )
        workgroup = re.search(
            r"@workgroup_size\s*\(\s*(\d+)\s*(?:,\s*(\d+))?\s*(?:,\s*(\d+))?\s*\)",
            source,
        )
        if workgroup is None:
            issues.append(StaticIssue("missing-workgroup-size", "missing @workgroup_size"))
        elif math_spec:
            actual = tuple(int(value or 1) for value in workgroup.groups())
            if actual != math_spec.workgroup_dimensions:
                issues.append(
                    StaticIssue(
                        "workgroup-mismatch",
                        f"shader declares {actual}, expected {math_spec.workgroup_dimensions}",
                    )
                )

        declarations = re.finditer(
            r"@group\((\d+)\)\s*@binding\((\d+)\)", source
        )
        declared = {(int(match.group(1)), int(match.group(2))) for match in declarations}
        for binding in artifact.bind_group_layouts:
            if (binding.group, binding.binding) not in declared:
                issues.append(
                    StaticIssue(
                        "binding-missing",
                        f"binding {binding.group}:{binding.binding} is not declared",
                    )
                )
        if "global_invocation_id" in source and not re.search(
            r"\bif\s*\([^)]*(?:>=|<)", source, flags=re.DOTALL
        ):
            issues.append(
                StaticIssue(
                    "unguarded-dispatch",
                    "global invocation id is used without a visible bounds guard",
                )
            )
        for match in re.finditer(r"\bvec3\s*<", source):
            prefix = source[max(0, match.start() - 80) : match.start()]
            if "struct" in prefix and "pad" not in prefix.lower():
                issues.append(
                    StaticIssue(
                        "vec3-alignment-review",
                        "vec3 structure field requires explicit 16-byte alignment review",
                        "warning",
                        _line_for(source, match.start()),
                    )
                )
        return issues


def analyze_shader(
    artifact: ShaderArtifact, math_spec: MathSpec | None = None
) -> list[StaticIssue]:
    return WGSLStaticAnalyzer().analyze(artifact, math_spec)