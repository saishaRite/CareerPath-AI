import json
import os
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv()

SKILL_CATALOG = [
    "Python", "Java", "C++", "C", "JavaScript", "TypeScript", "SQL", "PostgreSQL",
    "HTML", "CSS", "React", "Node.js", "FastAPI", "Django", "Flask", "Git",
    "Data Structures", "Algorithms", "OOP", "REST APIs", "Docker", "AWS",
    "Machine Learning", "Deep Learning", "Pandas", "NumPy", "TensorFlow",
    "PyTorch", "Communication", "Problem Solving", "System Design", "Linux",
    "MongoDB", "Redis", "Testing", "Excel", "Power BI"
]


def gemini_is_configured() -> bool:
    return bool(os.getenv("GEMINI_API_KEY", "").strip())


def extract_skills(text: str) -> list[str]:
    low = (text or "").lower()
    found = []
    for skill in SKILL_CATALOG:
        pattern = re.escape(skill.lower())
        if re.search(r"(?<![a-z0-9])" + pattern + r"(?![a-z0-9])", low):
            found.append(skill)
    aliases = {
        "dsa": "Data Structures",
        "data structures and algorithms": "Data Structures",
    }
    for alias, canonical in aliases.items():
        if alias in low and canonical not in found:
            found.append(canonical)
    return sorted(set(found))


def _extract_json(raw: str) -> dict[str, Any] | None:
    """Parse JSON even if the provider wraps it in a Markdown code fence."""
    if not raw:
        return None
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                value = json.loads(cleaned[start:end + 1])
                return value if isinstance(value, dict) else None
            except json.JSONDecodeError:
                return None
    return None


def gemini_json(prompt: str) -> dict[str, Any] | None:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    try:
        from google import genai

        client = genai.Client(api_key=key)
        model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip() or "gemini-3.8-flash"
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config={"response_mime_type": "application/json", "temperature": 0.2},
        )
        return _extract_json(response.text or "")
    except Exception as exc:
        # Keep the server alive if the external AI service is unavailable.
        print(f"Gemini request failed: {type(exc).__name__}: {exc}")
        return None


def _as_string_list(value: Any, limit: int = 6) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(item.strip()[:500])
        if len(result) >= limit:
            break
    return result


def analyze(target_role, job_description, resume_text, manual_skills):
    jd_skills = extract_skills(job_description)
    resume_skills = extract_skills(resume_text)
    current = sorted(set(resume_skills + [s for s in manual_skills if s in SKILL_CATALOG]))
    if not current:
        current = ["Communication", "Problem Solving"]
    if not jd_skills:
        jd_skills = ["Python", "SQL", "Data Structures", "Git", "Communication"]

    current_lower = {x.lower() for x in current}
    missing = [s for s in jd_skills if s.lower() not in current_lower]
    matched = [s for s in jd_skills if s not in missing]
    score = round(100 * len(matched) / max(1, len(jd_skills)))

    prompt = f"""
Return one valid JSON object with these keys:
summary (string), strengths (array of strings), priority_gaps (array of strings),
recommendations (array of strings).
Analyze the student's profile conservatively. Do not claim a skill is proven merely
because a keyword appears. Distinguish detected keywords from demonstrated ability.
Target role: {target_role}
Job description: {job_description[:7000]}
Resume text: {resume_text[:5000]}
Current skills supplied: {current}
Missing skills from detected job-description terms: {missing}
Do not invent qualifications, experience, projects, or job readiness.
"""
    ai = gemini_json(prompt)
    if ai:
        summary = str(ai.get("summary") or "Your profile contains relevant skills and areas to develop.")
        strengths = _as_string_list(ai.get("strengths")) or matched[:5] or current[:3]
        priority_gaps = _as_string_list(ai.get("priority_gaps")) or missing[:5]
        recommendations = _as_string_list(ai.get("recommendations"), 8)
        mode = "Gemini AI"
    else:
        summary = (
            f"You have {len(matched)} of {len(jd_skills)} detected role-skill keywords. "
            "Keyword matching is only an initial screen; validate these skills with projects and practical evidence."
        )
        strengths = matched[:5] or current[:3]
        priority_gaps = missing[:5]
        recommendations = [f"Study {s}, complete a practical exercise, and add evidence to a project." for s in missing[:4]]
        mode = "Local fallback"

    return {
        "target_role": target_role,
        "score": score,
        "current_skills": current,
        "required_skills": jd_skills,
        "matched_skills": matched,
        "missing_skills": missing,
        "summary": summary,
        "strengths": strengths,
        "priority_gaps": priority_gaps,
        "recommendations": recommendations,
        "mode": mode,
    }


def generate_roadmap(target_role, missing):
    prompt = f'''Return JSON only: {{"tasks":[{{"week":1,"title":"...","description":"...","resource":"https://..."}}]}}.
Create 6 practical learning tasks across 3 weeks for a student targeting {target_role}.
Prioritize these gaps: {missing}. Use reputable official documentation URLs where possible.'''
    ai = gemini_json(prompt)
    tasks = ai.get("tasks", []) if isinstance(ai, dict) else []
    if not isinstance(tasks, list):
        tasks = []
    if not tasks:
        focus = missing or ["Build a role-relevant project", "Practice technical communication"]
        tasks = []
        for i in range(6):
            skill = focus[i % len(focus)]
            resource = (
                "https://developer.mozilla.org/"
                if skill in ["HTML", "CSS", "JavaScript"]
                else "https://www.google.com/search?q=" + str(skill).replace(" ", "+") + "+official+documentation"
            )
            tasks.append({
                "week": i // 2 + 1,
                "title": f"{skill}: focused practice",
                "description": f"Study the fundamentals of {skill}, complete exercises, and write a short summary of what you learned.",
                "resource": resource,
            })
    return tasks[:12]


def recommend_projects(target_role, missing):
    prompt = f'''Return JSON only: {{"projects":[{{"title":"...","description":"...","skills":["..."],"difficulty":"Beginner"}}]}}.
Suggest 3 realistic portfolio projects for a student targeting {target_role}. Address these gaps: {missing}.
Do not claim that a project has already been built.'''
    ai = gemini_json(prompt)
    projects = ai.get("projects", []) if isinstance(ai, dict) else []
    if isinstance(projects, list) and projects:
        return projects[:5]
    focus = missing[:3] or ["problem solving", "communication"]
    return [{
        "title": f"{target_role} Starter Project",
        "description": f"Build a small usable application that demonstrates {', '.join(focus)}. Include a README, tests, and screenshots.",
        "skills": focus,
        "difficulty": "Beginner",
    }]


def _local_interview_evaluation(role: str, question: str, answer: str) -> dict[str, Any]:
    """Content-aware fallback. It is deliberately labelled as non-AI evaluation."""
    text = answer.lower()
    words = re.findall(r"\b[\w+#.-]+\b", answer)
    word_count = len(words)

    technical_terms = [
        "database", "sql", "normalization", "constraint", "primary key", "foreign key",
        "api", "endpoint", "algorithm", "complexity", "time complexity", "space complexity",
        "testing", "test case", "debug", "cache", "authentication", "validation",
        "trade-off", "tradeoff", "performance", "scalability", "index", "transaction",
        "python", "java", "c++", "react", "fastapi", "node.js", "git", "docker",
    ]
    found_terms = [term for term in technical_terms if term in text]
    has_example = any(term in text for term in ["for example", "for instance", "such as", "e.g.", "in my project"])
    has_tradeoff = any(term in text for term in ["trade-off", "tradeoff", "however", "instead", "compared with", "on the other hand"])
    has_result = any(term in text for term in ["result", "improved", "reduced", "faster", "because", "therefore"])
    has_direct_start = any(text.startswith(term) for term in ["i built", "i designed", "the project", "my project", "i implemented", "a "])

    score = 25
    score += min(20, word_count // 5)
    score += min(25, len(found_terms) * 5)
    score += 10 if has_example else 0
    score += 10 if has_tradeoff else 0
    score += 10 if has_result else 0
    score += 5 if has_direct_start else 0
    score = max(10, min(100, score))

    strengths = []
    if word_count >= 25:
        strengths.append(f"You provided a substantive response ({word_count} words), giving the evaluator material to assess.")
    if found_terms:
        strengths.append("You used relevant technical concepts: " + ", ".join(found_terms[:6]) + ".")
    if has_example:
        strengths.append("You attempted to ground the explanation in an example.")
    if not strengths:
        strengths.append("You identified the general subject of your answer, but need more technical detail to demonstrate understanding.")

    improvements = []
    if word_count < 60:
        improvements.append("Develop the answer further: explain what you built, how it works, and your individual contribution.")
    if not found_terms:
        improvements.append("Include precise technical concepts, components, tools, or design decisions relevant to the question.")
    if not has_example:
        improvements.append("Add one concrete example from your project, including the problem and the implementation you chose.")
    if not has_tradeoff:
        improvements.append("Explain at least one trade-off: what you chose, what alternative you considered, and why.")
    if not has_result:
        improvements.append("State the outcome or how you would measure whether the solution worked.")
    if not improvements:
        improvements.append("Improve precision by quantifying the result and explaining one limitation or next step.")

    model_answer = (
        "Use this structure for your next attempt: (1) state the project and the problem; "
        "(2) describe the architecture and your specific implementation; "
        "(3) explain one technical decision and the alternative you rejected; "
        "(4) give a concrete example or result; and (5) identify one limitation you would improve."
    )
    return {
        "score": score,
        "strengths": strengths[:5],
        "improvements": improvements[:6],
        "model_answer": model_answer,
        "dimensions": {
            "relevance": None,
            "technical_accuracy": None,
            "clarity": None,
            "examples": None,
            "trade_offs": None,
        },
        "evaluation_mode": "Local fallback (Gemini unavailable)",
        "notice": "This is a local heuristic evaluation, not an AI assessment. Check the server terminal for the Gemini error.",
    }

def evaluate_answer(role, question, answer):
    prompt = f"""
You are a strict technical interviewer evaluating a student's mock interview answer.

Evaluate the answer using these five criteria:
1. relevance: Does it directly answer the question?
2. technical_accuracy: Are the technical concepts correct?
3. clarity: Is the explanation structured and understandable?
4. examples: Does it contain concrete implementation examples?
5. trade_offs: Does it explain technical decisions, alternatives, and compromises?

Return ONLY valid JSON in this exact structure:

{{
    "rubric": {{
        "relevance": 0,
        "technical_accuracy": 0,
        "clarity": 0,
        "examples": 0,
        "trade_offs": 0
    }},
    "strengths": [
        "Specific strength from the actual answer"
    ],
    "improvements": [
        "Specific actionable improvement"
    ],
    "model_answer": "A technically strong improved answer."
}}

Rules:
- Every rubric score must be an integer from 0 to 10.
- Be strict and fair. Do not reward irrelevant length.
- Do not give high scores merely because technical keywords are mentioned.
- Identify incorrect or unsupported technical claims.
- Use only technologies and implementation details established in the student's answer.
- Never invent frameworks, databases, testing tools, performance results, or achievements.
- If information is missing, explicitly say it needs to be specified.
- The improved answer must directly address the question.
- Explain at least one actual technical trade-off.
- Do not use placeholders such as [Database] or [Framework].
- Provide 2-4 specific strengths and 2-4 actionable improvements.

Student's target role: {role}
Interview question: {question}
Student's answer: {answer[:5000]}
"""

    ai = gemini_json(prompt)

    if isinstance(ai, dict):
        try:
            rubric_data = ai.get("rubric", {})

            if not isinstance(rubric_data, dict):
                rubric_data = {}

            def get_score(key):
                try:
                    value = int(rubric_data.get(key, ai.get(key, 5)))
                    return max(0, min(10, value))
                except (ValueError, TypeError):
                    return 5

            rubric = {
                "relevance": get_score("relevance"),
                "technical_accuracy": get_score("technical_accuracy"),
                "clarity": get_score("clarity"),
                "examples": get_score("examples"),
                "trade_offs": get_score("trade_offs")
            }

            # Calculate the total from the five rubric scores.
            total_score = round(sum(rubric.values()) * 2)

            strengths = ai.get("strengths", [])
            improvements = ai.get("improvements", [])
            model_answer = str(ai.get("model_answer", "")).strip()

            if not isinstance(strengths, list):
                strengths = []

            if not isinstance(improvements, list):
                improvements = []

            # Reject generic template answers containing placeholders.
            has_placeholders = bool(
                re.search(r"\[[^\]]+\]", model_answer)
            )

            if not model_answer or has_placeholders:
                model_answer = (
                    "A reliable improved answer could not be generated. "
                    "Please try evaluating again."
                )

            return {
                "score": total_score,
                "rubric": rubric,
                **rubric,
                "strengths": [str(x) for x in strengths[:4]],
                "improvements": [str(x) for x in improvements[:4]],
                "model_answer": model_answer,
                "mode": "Gemini AI",
                "evaluation_mode": "AI"
            }

        except Exception as exc:
            print("Gemini evaluation processing failed:", str(exc))

    # Honest local fallback: this is not an AI assessment.
    words = len(answer.split())
    has_example = any(
        word in answer.lower()
        for word in ["for example", "implemented", "using", "because"]
    )
    has_tradeoff = any(
        word in answer.lower()
        for word in ["trade-off", "tradeoff", "instead of", "however"]
    )

    rubric = {
        "relevance": min(7, max(2, words // 20)),
        "technical_accuracy": 4,
        "clarity": min(7, max(2, words // 25)),
        "examples": 5 if has_example else 2,
        "trade_offs": 5 if has_tradeoff else 2
    }

    return {
        "score": round(sum(rubric.values()) * 2),
        "rubric": rubric,
        **rubric,
        "strengths": [
            "You submitted a written response.",
            "Your answer contains material that can be developed further."
        ],
        "improvements": [
            "Include a specific implementation example.",
            "Explain the technical reasoning behind your decisions.",
            "Discuss the alternatives and limitations of your approach."
        ],
        "model_answer": (
            "Local fallback cannot generate a technically verified model answer. "
            "Please try again when Gemini is available."
        ),
        "mode": "Local fallback",
        "evaluation_mode": "Fallback"
    }
