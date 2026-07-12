# Cognion

Cognion turns paper-reading conversations into durable cognitive traces that can guide later answers, notes, and knowledge-graph workflows.

## Language

**User**:
A person with a Cognion identity who exclusively owns their papers, folders, conversations, notes, and knowledge graph. A User is identified by a verified email address.
_Avoid_: Account, profile

**Email Verification**:
Proof that a User controls the email address associated with their Cognion identity. Registration does not establish an active identity until Email Verification succeeds.
_Avoid_: Login code, passwordless login

**User Space**:
The private collection of papers, folders, conversations, notes, and knowledge graph belonging exclusively to one **User**. Cognion has no shared or cross-user resources.
_Avoid_: Workspace, tenant, shared library

**User Metadata**:
The editable profile associated one-to-one with a **User**, consisting of their display name, avatar, locale, and timezone. It excludes identity credentials and verification state.
_Avoid_: User, account, authentication data

**Cognitive Context**:
A concise set of prior knowledge, notes, and user-understanding signals that should materially influence the next answer. It is not a raw dump of all related notes or graph nodes.
_Avoid_: Retrieval results, search hits, memory dump

**Cognitive Context Selection**:
The act of deciding which parts of the user's existing knowledge and notes are relevant enough to shape an answer. It runs for paper-bound Conversation Answers and may produce an empty brief when no prior context would change the answer.
_Avoid_: Full retrieval, keyword search

**Decision-Impacting Context**:
Prior context that would change how the assistant answers: explaining background, correcting a misunderstanding, connecting to prior knowledge, asking a follow-up, or choosing a more direct answer. Topic similarity alone is not Decision-Impacting Context.
_Avoid_: Related content, same-topic material

**Cognitive Context Brief**:
A compact, structured brief produced by Cognitive Context Selection for a Conversation Answer. It can recommend an answer strategy, relevant mental models, misunderstandings, knowledge connections, follow-up questions, and source references, but it does not override the current question, quote, paper context, or the assistant's duty to answer accurately.
_Avoid_: Raw note bundle, retrieved document dump

**Cognitive Context Scope**:
The body of prior notes and knowledge that may be considered for Cognitive Context Selection. It spans the user's global knowledge, with the current session and current paper carrying stronger relevance than broader knowledge.
_Avoid_: Current-paper-only memory, session-only memory

**Retrieval Description**:
A compact description generated with a note that explains when the note should be recalled for future Cognitive Context Selection. It is an index card for the system, not a human-facing summary or the full note content.
_Avoid_: Note summary, note content excerpt

**Conversation History**:
The recent turns in the active reading conversation that preserve local dialogue continuity. It is separate from Cognitive Context and only becomes durable prior knowledge after being externalized into notes or knowledge units.
_Avoid_: Cognitive Context candidate, long-term memory

**Conversation Answer**:
An answer given in the active reading conversation, shaped by the current question, selected paper context, quote, Conversation History, and any selected Cognitive Context.
_Avoid_: Generic QA response

## Example Dialogue

Developer: "Should we pass every related note into the next answer?"

Domain Expert: "No. Only pass Cognitive Context: the knowledge and note fragments that would change how the assistant explains, challenges, or follows up."

Developer: "So if a note is merely about the same paper topic, it is not enough?"

Domain Expert: "Right. Cognitive Context Selection should keep the Conversation Answer focused on what affects the user's current understanding."

Developer: "What usually counts as Decision-Impacting Context?"

Domain Expert: "A previous confusion, partial mental model, unresolved follow-up question, or linked knowledge unit that changes the answer strategy."

Developer: "Should the conversation agent receive the full retrieved notes?"

Domain Expert: "No. It should receive a Cognitive Context Brief, so it can answer with the right strategy without redoing context selection."

Developer: "Should Cognitive Context Selection only look at the current paper?"

Domain Expert: "No. The Cognitive Context Scope is global, but current-session and current-paper knowledge should be much stronger signals than distant prior notes."

Developer: "Should raw current-session turns be selected by Cognitive Context Selection?"

Domain Expert: "No. They are Conversation History. Cognitive Context Selection should work on durable notes and knowledge units, then produce a brief separately."

Developer: "Should retrieval scan full note content first?"

Domain Expert: "No. It should first scan each note's Retrieval Description, then expand details only for matched notes."

Developer: "Can a newly registered User sign in before confirming their email?"

Domain Expert: "No. Registration creates an unverified identity; Email Verification must succeed before that User can sign in and access owned Cognion data."

Developer: "Can one User open a paper or note owned by another User if they know its identifier?"

Domain Expert: "No. Every resource belongs to exactly one User Space, and resources are never visible across User Spaces."

Developer: "Does changing a display name change the User's login identity?"

Domain Expert: "No. Display name belongs to User Metadata; identity credentials and Email Verification belong to the User."
