Here's an audit of the provided translations against your glossary:

---

### Wrong terms

No direct "wrong terms" were found where an English term explicitly listed in the glossary was translated incorrectly. The existing translations for glossary terms are generally accurate.

---

### Inconsistent translations

No inconsistencies were found where a single English term from the glossary was translated into multiple different Polish terms.
For example, "Schedule" and "Timetable" are both consistently translated as "Plan zajęć", which is acceptable if they are considered synonymous in Polish context.

---

### Suggestions

The following suggestions address missing translations for glossary terms, potential ambiguities, and minor issues:

1.  **Missing Glossary Terms:**
    *   **Deactivate**: There is no translation for the glossary term "Deactivate".
    *   **Download**: There is no translation for the glossary term "Download".
    *   **Head teacher**: The glossary term "Head teacher" is missing a direct translation. The term `role.main_teacher` is translated as "Wychowawca" (homeroom teacher/class tutor), which is a different role than a Head teacher (Dyrektor Szkoły).
    *   **Middle name**: There is no translation for the glossary term "Middle name".
    *   **Status**: There is no translation for the glossary term "Status".

2.  **Clarification/Consistency for "Lesson" / "Course":**
    *   The glossary lists "Lesson". The translations use "zajęcia" (which can mean classes, lessons, or courses) for keys related to `sched.course.*` (e.g., `sched.course.info`, `sched.course.duration`).
    *   **Suggestion**: Clarify if "zajęcia" is the intended standard translation for "Lesson". If "Course" is also a distinct entity, consider adding it to the glossary and defining its translation.

3.  **General "Export" Term:**
    *   The glossary includes "Export". The translations currently provide `action.pdf`: "Eksportuj do PDF" (Export to PDF), which uses the correct verb "Eksportuj".
    *   **Suggestion**: Consider adding a general `action.export` key to cover generic export functionality, ensuring "Eksportuj" is consistently used as the verb for "Export".

4.  **"Resource" (Singular Form):**
    *   The plural form "Resources" is correctly implied and used in contexts like `sched.course.assign_resources`: "Przypisz zasoby" (Assign resources).
    *   **Suggestion**: Add an explicit key for the singular "Resource", e.g., `resource`: "Zasób", for comprehensive coverage.

5.  **Truncated Translation:**
    *   The translation for `admin.sites.none` is incomplete: "Nie masz żadnych mie".
    *   **Suggestion**: Correct this to "Nie masz żadnych miejsc" (You don't have any sites).