 PIPELINE EXPLANATION


## Translation Pipeline Design

The translation pipeline is designed as a modular command-line system that automates the generation, validation, and maintenance of multilingual JSON translation files.

### Step 1: Data Source

The French translation files (`fr_webapp.json` and `fr_login.json`) act as the reference source of truth. All other languages are derived from these files.

---

### Step 2: Chunk-Based Processing

Since translation files contain more than 1200 keys, the pipeline splits them into smaller chunks.

This ensures:
- reliable AI processing
- reduced API failure risk
- easier validation

---

### Step 3: AI-Based Translation

Each chunk is sent to Gemini (via Vertex AI) with:
- strict translation instructions
- glossary constraints
- formatting preservation rules

The model returns translated JSON values while keeping keys unchanged.

---

### Step 4: Validation Layer

After each translation, the pipeline performs validation checks:

- Key consistency (no missing or extra keys)
- Placeholder preservation (`{name}`, `%s`, etc.)
- HTML tag consistency (`<br>`, `<b>`, etc.)
- Detection of untranslated values

If validation fails, the chunk is retried automatically.

---

### Step 5: Retry and Error Handling

The system includes:
- retry mechanism (up to 5 attempts)
- exponential backoff
- detection of retryable errors (e.g., 429, timeouts)

This improves robustness when interacting with external APIs.

---

### Step 6: Language File Generation

Validated chunks are merged into final translation files:
- `<lang>_webapp.json`
- `<lang>_login.json`

---

### Step 7: Sync Missing Keys

To maintain consistency over time:
- missing keys are detected by comparing with the French reference
- only missing entries are translated and inserted

This avoids full regeneration and reduces API usage.

---

### Step 8: Audit System

An audit module analyzes existing translations and generates reports highlighting:
- inconsistent terms
- glossary violations
- potential translation issues

Reports are generated in Markdown format for easy review.

---

### Overall Pipeline Flow

French Source → Chunking → AI Translation → Validation → Merge → Output JSON  
                                                                                 ↓  
                                                                        Audit / Sync

---

This architecture ensures scalability, consistency, and partial automation while maintaining cont
