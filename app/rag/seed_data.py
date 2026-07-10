"""
Starter prep material for the NEXUS RAG index. Each chunk is short (a few
sentences) so retrieval pulls focused, relevant context rather than a wall
of text. Topics match what the frontend's topic field expects (free text,
so keep these exact strings in sync with what you type into the UI).

This is a starting set -- add your own chunks (from your own notes, past
interview questions, course material, etc.) via `upsert_material()` as you
go. Keep `id`s unique across the whole index.
"""

SEED_CHUNKS = [
    # --- System Design ---
    {
        "id": "sysdes-001",
        "topic": "System Design",
        "text": (
            "CAP theorem: a distributed system can only guarantee two of "
            "Consistency, Availability, and Partition tolerance at once. "
            "Since network partitions are unavoidable in practice, real "
            "systems choose between CP (favor consistency, e.g. HBase, "
            "etcd) and AP (favor availability, e.g. Cassandra, DynamoDB) "
            "when a partition occurs."
        ),
    },
    {
        "id": "sysdes-002",
        "topic": "System Design",
        "text": (
            "Load balancing strategies: round robin (simple, ignores server "
            "load), least connections (routes to the server with fewest "
            "active connections), and consistent hashing (minimizes "
            "re-mapping when nodes are added/removed, important for caches "
            "and sharded databases)."
        ),
    },
    {
        "id": "sysdes-003",
        "topic": "System Design",
        "text": (
            "Caching patterns: cache-aside (app checks cache, falls back to "
            "DB and populates cache on miss), write-through (writes go to "
            "cache and DB together, stronger consistency but slower "
            "writes), and write-behind (writes go to cache first and are "
            "flushed to DB asynchronously, faster but risks data loss)."
        ),
    },
    {
        "id": "sysdes-004",
        "topic": "System Design",
        "text": (
            "Database sharding splits a large table across multiple "
            "machines by a shard key (e.g. user_id). Range-based sharding "
            "is simple but can create hotspots; hash-based sharding "
            "distributes load evenly but makes range queries expensive. "
            "Resharding is the hard part -- consistent hashing helps."
        ),
    },
    {
        "id": "sysdes-005",
        "topic": "System Design",
        "text": (
            "Message queues (Kafka, RabbitMQ, SQS) decouple producers from "
            "consumers and smooth out traffic spikes. Kafka is log-based "
            "and built for high-throughput streaming with replay; RabbitMQ "
            "is a traditional broker better suited to complex routing and "
            "per-message acknowledgment semantics."
        ),
    },
    {
        "id": "sysdes-006",
        "topic": "System Design",
        "text": (
            "Designing a URL shortener: generate a short code (base62 "
            "encoding of an auto-incrementing ID, or a hash with collision "
            "checks), store the mapping in a key-value store for O(1) "
            "lookups, and use a read-through cache in front of the DB since "
            "reads vastly outnumber writes."
        ),
    },
    # --- Python DSA ---
    {
        "id": "dsa-001",
        "topic": "Python DSA",
        "text": (
            "Two-pointer technique works well on sorted arrays or linked "
            "lists: one pointer scans from the start, another from the end "
            "(or a slow/fast pair), letting you solve problems like pair "
            "sum, removing duplicates, or cycle detection in O(n) time and "
            "O(1) extra space."
        ),
    },
    {
        "id": "dsa-002",
        "topic": "Python DSA",
        "text": (
            "Sliding window is the go-to pattern for 'longest/shortest "
            "substring or subarray satisfying X' problems. Expand the "
            "right edge to grow the window, shrink from the left when a "
            "constraint is violated, and track the best answer as you go -- "
            "this turns an O(n^2) brute force into O(n)."
        ),
    },
    {
        "id": "dsa-003",
        "topic": "Python DSA",
        "text": (
            "Dictionaries in Python (hash maps) give average O(1) "
            "insert/lookup/delete. They're the first tool to reach for "
            "when a problem involves counting frequencies, checking for "
            "'have I seen this before', or needing a fast complement "
            "lookup (e.g. two-sum)."
        ),
    },
    {
        "id": "dsa-004",
        "topic": "Python DSA",
        "text": (
            "Binary search isn't just for sorted arrays -- it applies to "
            "any monotonic predicate. 'Find the minimum value of X such "
            "that condition(X) is true' is a strong signal to binary "
            "search over the answer space itself, not just the input array."
        ),
    },
    {
        "id": "dsa-005",
        "topic": "Python DSA",
        "text": (
            "Recursion + memoization (top-down DP) is often easier to "
            "reason about than bottom-up tabulation: write the brute-force "
            "recursive solution first, identify overlapping subproblems, "
            "then add an `lru_cache` or explicit dict cache keyed on the "
            "function's arguments."
        ),
    },
    {
        "id": "dsa-006",
        "topic": "Python DSA",
        "text": (
            "Graph traversal choice matters: BFS finds shortest paths in "
            "unweighted graphs and explores level-by-level (good for "
            "'minimum steps' problems); DFS is better for exhaustive "
            "search, cycle detection, and topological sort, and uses less "
            "memory for deep graphs since it doesn't hold a full frontier."
        ),
    },
    # --- Behavioral ---
    {
        "id": "behav-001",
        "topic": "Behavioral",
        "text": (
            "The STAR method structures behavioral answers: Situation "
            "(brief context), Task (what you specifically needed to do), "
            "Action (what you actually did -- this should be the bulk of "
            "the answer), Result (the measurable outcome, and ideally what "
            "you'd do differently)."
        ),
    },
    {
        "id": "behav-002",
        "topic": "Behavioral",
        "text": (
            "For 'tell me about a conflict with a teammate' questions, "
            "interviewers are listening for whether you addressed the "
            "disagreement directly and professionally, focused on the "
            "problem rather than the person, and reached a resolution -- "
            "not for who was 'right'."
        ),
    },
    {
        "id": "behav-003",
        "topic": "Behavioral",
        "text": (
            "'Tell me about a time you failed' answers land best when you "
            "own the mistake plainly (no excuses or blame-shifting), "
            "explain the concrete root cause you identified, and describe "
            "what changed in how you work as a result."
        ),
    },
    {
        "id": "behav-004",
        "topic": "Behavioral",
        "text": (
            "When asked 'why this company', avoid generic praise. Tie your "
            "answer to something specific -- a product decision, "
            "engineering blog post, or technical challenge the company has "
            "publicly discussed -- and connect it to what you personally "
            "want to work on next."
        ),
    },
    {
        "id": "behav-005",
        "topic": "Behavioral",
        "text": (
            "For 'describe a time you had to learn something quickly', a "
            "strong answer names the specific resource or strategy you "
            "used (not just 'I read the docs'), the timeline you were "
            "under, and how you validated you'd actually learned it well "
            "enough to apply it."
        ),
    },
    # --- Machine Learning ---
    {
        "id": "ml-001",
        "topic": "Machine Learning",
        "text": (
            "Bias-variance tradeoff: high-bias models (e.g. linear "
            "regression on nonlinear data) underfit and have high training "
            "error; high-variance models (e.g. deep trees) overfit, "
            "memorizing noise and generalizing poorly. Regularization, "
            "more data, and cross-validation are the standard levers to "
            "balance the two."
        ),
    },
    {
        "id": "ml-002",
        "topic": "Machine Learning",
        "text": (
            "Precision vs recall: precision is 'of the items I flagged "
            "positive, how many were actually positive' (cost of false "
            "positives), recall is 'of all actual positives, how many did "
            "I catch' (cost of false negatives). Which one to optimize for "
            "depends entirely on which error is more expensive for the use "
            "case -- e.g. spam filtering favors precision, cancer "
            "screening favors recall."
        ),
    },
    {
        "id": "ml-003",
        "topic": "Machine Learning",
        "text": (
            "Attention in transformers computes a weighted sum of value "
            "vectors, where weights come from the scaled dot product of "
            "query and key vectors passed through softmax. Multi-head "
            "attention runs several of these in parallel with different "
            "learned projections, letting the model attend to different "
            "types of relationships simultaneously."
        ),
    },
    {
        "id": "ml-004",
        "topic": "Machine Learning",
        "text": (
            "RAG (retrieval-augmented generation) grounds an LLM's answer "
            "in retrieved documents rather than relying purely on "
            "parametric memory. It reduces hallucination and lets you "
            "update knowledge without retraining, but retrieval quality "
            "(chunking strategy, embedding model, reranking) usually "
            "matters more to end results than the generator model choice."
        ),
    },
    {
        "id": "ml-005",
        "topic": "Machine Learning",
        "text": (
            "Cross-validation (typically k-fold) gives a more reliable "
            "estimate of a model's generalization performance than a "
            "single train/test split, since every data point gets used "
            "for both training and validation across folds. Always fit "
            "preprocessing steps (scaling, imputation) only on the "
            "training fold to avoid data leakage."
        ),
    },
    # --- SQL ---
    {
        "id": "sql-001",
        "topic": "SQL",
        "text": (
            "INNER JOIN returns only matching rows from both tables; LEFT "
            "JOIN returns all rows from the left table plus matches from "
            "the right (NULLs where there's no match). A common bug is "
            "using LEFT JOIN but then filtering on a right-table column in "
            "the WHERE clause, which silently turns it back into an INNER "
            "JOIN."
        ),
    },
    {
        "id": "sql-002",
        "topic": "SQL",
        "text": (
            "Window functions (e.g. RANK() OVER (PARTITION BY ... ORDER BY "
            "...)) let you compute per-row rankings, running totals, or "
            "comparisons to neighboring rows without collapsing the result "
            "set the way GROUP BY does -- essential for 'top N per group' "
            "queries."
        ),
    },
    {
        "id": "sql-003",
        "topic": "SQL",
        "text": (
            "Indexes speed up reads (especially WHERE, JOIN, and ORDER BY "
            "on indexed columns) but slow down writes, since every insert/"
            "update must also update the index. A composite index's "
            "column order matters -- it can only be used efficiently as a "
            "left-to-right prefix of the query's filter columns."
        ),
    },
]
