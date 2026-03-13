# Visits Heartbeat

- Scan for leads with status `qualified` and no recent slot proposal.
- Prioritize `hot` and `medium` leads over `weak` ones when proposing new visit work.
- Scan for leads with status `visit_proposed` and no reply after a reasonable delay.
- Check the next 7 days for free visit windows inside preferred visit hours.
- Prefer grouping qualified leads by commune or nearby zone before suggesting isolated visits.
- If a good slot or cluster exists, message the agent on Telegram with one concrete proposal.
- If the calendar is empty, still suggest a reasonable next slot instead of waiting.
- Escalate urgent next-day requests if calendar visibility is incomplete.
- Keep messages short and operational: `ok / autre heure / autre jour`.
- If nothing needs attention, reply `HEARTBEAT_OK`.
