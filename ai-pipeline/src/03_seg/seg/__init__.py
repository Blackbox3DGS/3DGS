def run(context):
    """Stage 03: Segmentation & Tracking.

    Also sets target_ids to all dynamic objects by default
    (Stage 3.5 user selection is deferred).
    """
    context["artifacts"]["target_ids"] = "all_dynamic"
    raise NotImplementedError("Stage 03 not implemented yet.")
