"""Reusable cleaning pipeline for the mobile-money agent transaction extract.

Usage
-----
    import pandas as pd
    from cleaning_pipeline import clean_agent_data

    txns = pd.read_csv("agent_transactions.csv")
    agents = pd.read_csv("agents.csv")
    clean_df, log = clean_agent_data(txns, agents)

Every rule is applied in code (no hard-coded row numbers, no manual edits), so
next week's extract can be cleaned with the same single call.
"""
import numpy as np
import pandas as pd

# The only two transaction types the business recognises.
CANONICAL_TYPES = {"deposit": "Deposit", "withdrawal": "Withdrawal"}


def clean_agent_data(txns, agents):
    """Clean a raw agent-transaction extract and merge it with the agent register.

    Rules applied, in order (each one writes a line to the log):

    1. Consistency  - trim whitespace in id/text columns; standardise
       ``txn_type`` to exactly "Deposit" / "Withdrawal".
    2. Validity     - convert ``amount`` to numeric (blank, "N/A", text and
       non-positive values become missing) and ``txn_date`` to datetime
       (``YYYY/MM/DD`` and ``YYYY-MM-DD`` both accepted; anything else -> NaT).
    3. Uniqueness   - one row per ``txn_id``. Copies of the same transaction are
       collapsed even when a field differs between copies; the copy with a
       registered agent and a recorded amount is kept.
    4. Completeness - FLAG missing/invalid amounts (``amount_imputed``), then fill
       them with the median valid, non-outlier amount for the same ``txn_type``.
    5. Accuracy     - flag IQR outliers (``is_outlier``) on the genuine amounts,
       computed *before* imputation. Outliers are flagged, never deleted.
    6. Consistency  - left-join to the agent register (validated many-to-one) so
       no transaction is lost; unknown agents get county "Unknown" and
       ``unknown_agent=True``.

    Parameters
    ----------
    txns : pandas.DataFrame
        Raw transactions: txn_id, agent_id, txn_type, amount, txn_date.
    agents : pandas.DataFrame
        Agent register: agent_id, county, onboarded.

    Returns
    -------
    (clean_df, log) : (pandas.DataFrame, list[str])
        ``clean_df`` has one row per transaction, a numeric ``amount``, a
        datetime ``txn_date``, the flags ``amount_imputed``, ``is_outlier`` and
        ``unknown_agent``, and the agent ``county`` / ``onboarded`` columns.
        ``log`` is a list of human-readable lines describing every change.
    """
    log = []
    df = txns.copy().reset_index(drop=True)
    reg = agents.copy().reset_index(drop=True)
    n_raw = len(df)
    log.append(f"Input: {n_raw} transaction rows, {len(reg)} agents in register")

    # ------------------------------------------------------------------ 1
    for col in ["txn_id", "agent_id", "txn_type"]:
        df[col] = df[col].astype("string").str.strip()
    reg["agent_id"] = reg["agent_id"].astype("string").str.strip()
    reg["county"] = reg["county"].astype("string").str.strip().str.title()

    raw_type = df["txn_type"]
    df["txn_type"] = raw_type.str.lower().map(CANONICAL_TYPES)
    n_recoded = int((df["txn_type"].ne(raw_type) & df["txn_type"].notna()).sum())
    n_unmapped = int(df["txn_type"].isna().sum())
    log.append(f"Consistency: standardised txn_type on {n_recoded} rows to "
               f"{sorted(CANONICAL_TYPES.values())}; {n_unmapped} unmappable values left missing")

    # ------------------------------------------------------------------ 2
    raw_amount = df["amount"]
    was_missing = raw_amount.isna()                       # blank cell or "N/A" read as NaN
    text = raw_amount.astype("string").str.replace(",", "", regex=False).str.strip()
    numeric = pd.to_numeric(text, errors="coerce")
    invalid_text = numeric.isna() & ~was_missing          # non-numeric strings
    non_positive = numeric.le(0).fillna(False)
    numeric = numeric.mask(non_positive)
    df["amount"] = numeric.astype(float)
    log.append(f"Validity: amount converted to numeric; {int(was_missing.sum())} missing "
               f"(blank or 'N/A'), {int(invalid_text.sum())} non-numeric strings, "
               f"{int(non_positive.sum())} non-positive values -> set to missing")

    date_text = df["txn_date"].astype("string").str.strip()
    n_slash = int(date_text.str.contains("/", regex=False, na=False).sum())
    df["txn_date"] = pd.to_datetime(date_text.str.replace("/", "-", regex=False),
                                    format="%Y-%m-%d", errors="coerce")
    n_bad_date = int(df["txn_date"].isna().sum())
    log.append(f"Validity: txn_date converted to datetime; {n_slash} rows used the "
               f"YYYY/MM/DD format and were normalised; {n_bad_date} unparseable dates left as NaT")

    # ------------------------------------------------------------------ 3
    n_exact = int(df.duplicated().sum())
    known = df["agent_id"].isin(reg["agent_id"])
    order = (pd.DataFrame({"known": ~known, "no_amount": df["amount"].isna()})
             .assign(pos=np.arange(len(df)))
             .sort_values(["known", "no_amount", "pos"]).index)
    deduped = df.loc[order].drop_duplicates(subset="txn_id", keep="first").sort_index()
    n_dupes = n_raw - len(deduped)
    log.append(f"Uniqueness: removed {n_dupes} duplicate transactions (one row kept per txn_id); "
               f"{n_exact} were exact full-row copies and {n_dupes - n_exact} differed in at least "
               f"one field, so drop_duplicates() alone would have missed them")
    df = deduped.reset_index(drop=True)

    # ------------------------------------------------------------------ 4 + 5
    valid = df["amount"]
    q1, q3 = valid.quantile([0.25, 0.75])
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    df["is_outlier"] = valid.notna() & ((valid < lower) | (valid > upper))
    log.append(f"Accuracy: IQR rule on {int(valid.notna().sum())} genuine amounts "
               f"(Q1={q1:,.0f}, Q3={q3:,.0f}, fences {lower:,.0f} to {upper:,.0f}); flagged "
               f"{int(df['is_outlier'].sum())} outliers (kept, not deleted)")

    df["amount_imputed"] = df["amount"].isna()
    typical = df["amount"].where(~df["is_outlier"])
    by_type = typical.groupby(df["txn_type"]).transform("median")
    fill = by_type.fillna(typical.median())
    df["amount"] = df["amount"].fillna(fill)
    medians = typical.groupby(df["txn_type"]).median().round(0).to_dict()
    log.append(f"Completeness: flagged and imputed {int(df['amount_imputed'].sum())} missing/invalid "
               f"amounts with the median non-outlier amount of the same txn_type {medians}")

    # ------------------------------------------------------------------ 6
    n_before = len(df)
    reg["onboarded"] = pd.to_datetime(reg["onboarded"], errors="coerce")
    df = df.merge(reg[["agent_id", "county", "onboarded"]], on="agent_id",
                  how="left", validate="many_to_one")
    assert len(df) == n_before, "merge changed the row count"
    df["unknown_agent"] = df["county"].isna()
    unknown_ids = sorted(df.loc[df["unknown_agent"], "agent_id"].unique())
    df["county"] = df["county"].fillna("Unknown")
    log.append(f"Consistency: left-joined to agent register ({n_before} rows before and after); "
               f"{int(df['unknown_agent'].sum())} transactions reference unknown agents {unknown_ids} "
               f"-> kept with county='Unknown' and unknown_agent=True")

    df = df[["txn_id", "agent_id", "txn_type", "amount", "txn_date",
             "amount_imputed", "is_outlier", "county", "unknown_agent", "onboarded"]]
    log.append(f"Output: {len(df)} rows (removed {n_raw - len(df)} of {n_raw})")
    return df, log
