import os
import re
import json
import zipfile
from datetime import datetime

SKILL_DIRS = [
    os.path.join(os.path.dirname(__file__), "skills"),
    os.path.join(os.path.dirname(__file__), "Skills"),
    "/data/skills",
]


def _parse_frontmatter(content: str):
    """Parse YAML-style frontmatter between --- and ---."""
    meta = {}
    body = content
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if match:
        fm_text, body = match.group(1), match.group(2)
        for line in fm_text.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip()
    return meta, body.strip()


def load_all_skills():
    """Scan all skill directories and return registry of skill_name -> metadata + content."""
    registry = {}

    for sdir in SKILL_DIRS:
        if not os.path.exists(sdir):
            continue

        for item in os.listdir(sdir):
            full_path = os.path.join(sdir, item)

            # 1. Unpacked folder containing SKILL.md
            if os.path.isdir(full_path):
                skill_md = os.path.join(full_path, "SKILL.md")
                if os.path.exists(skill_md):
                    try:
                        with open(skill_md, "r", encoding="utf-8", errors="replace") as f:
                            text = f.read()
                        meta, body = _parse_frontmatter(text)
                        sname = meta.get("name", item).lower()
                        registry[sname] = {
                            "name": sname,
                            "description": meta.get("description", "No description provided."),
                            "instructions": body,
                            "source_path": skill_md,
                        }
                    except Exception as e:
                        print(f"[Skills] Error loading {skill_md}: {e}")

            # 2. Packed .skill zip archive
            elif item.endswith(".skill") and os.path.isfile(full_path):
                try:
                    with zipfile.ZipFile(full_path, "r") as z:
                        for zname in z.namelist():
                            if zname.endswith("SKILL.md"):
                                text = z.read(zname).decode("utf-8", errors="replace")
                                meta, body = _parse_frontmatter(text)
                                sname = meta.get("name", item.replace(".skill", "")).lower()
                                if sname not in registry:
                                    registry[sname] = {
                                        "name": sname,
                                        "description": meta.get("description", "No description provided."),
                                        "instructions": body,
                                        "source_path": full_path,
                                    }
                except Exception as e:
                    print(f"[Skills] Error reading archive {full_path}: {e}")

    return registry


_REGISTRY = load_all_skills()


def refresh_skills():
    global _REGISTRY
    _REGISTRY = load_all_skills()
    return _REGISTRY


def get_skills_registry():
    return _REGISTRY


def get_skills_prompt_summary():
    """Format available skills for inclusion in the system prompt."""
    skills = get_skills_registry()
    if not skills:
        return ""

    lines = [
        "## SPECIALIZED SKILLS (Under `skills/` folder)",
        "You have specialized domain skills available that you can invoke via the `load_skill` tool when relevant:",
    ]
    for name, s in sorted(skills.items()):
        lines.append(f"- **`{name}`**: {s['description']}")
    lines.append("Call `load_skill(skill_name='...')` to load full guidelines when handling matching tasks.")
    return "\n".join(lines)


def load_skill_tool(skill_name: str):
    """Agent tool to load and activate a specialized skill from the skills folder."""
    skills = get_skills_registry()
    norm = skill_name.strip().lower()

    if norm not in skills:
        # Check partial match
        for k, v in skills.items():
            if norm in k or k in norm:
                norm = k
                break

    if norm in skills:
        skill = skills[norm]
        now_dt = datetime.now()
        extra_ctx = {}
        if "time" in norm or "date" in norm:
            extra_ctx = {
                "current_iso_time": now_dt.isoformat(),
                "current_formatted_date": now_dt.strftime("%A, %B %d, %Y, %I:%M:%S %p"),
                "current_year": str(now_dt.year),
            }

        return {
            "status": "success",
            "skill": norm,
            "instructions": skill["instructions"],
            **extra_ctx,
        }

    return {
        "status": "error",
        "message": f"Skill '{skill_name}' not found. Available skills: {list(skills.keys())}",
    }
