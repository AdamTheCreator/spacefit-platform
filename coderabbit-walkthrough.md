# CodeRabbit Hands-On Walkthrough

**Project:** Space Goose  
**Date:** July 28, 2026

---

## 1. Setup and First Attempt

I started with an existing project, Space Goose, and created a small frontend-only PR: a traffic-counts card that calls a ready backend endpoint.

- **PR:** [#81 — feat(traffic): add property traffic counts card](https://github.com/AdamTheCreator/spacefit-platform/pull/81)

The change was clean and self-contained:

- A React Query hook for the traffic-counts API
- A card component for loading, missing, and found states
- One-line integration into the property detail page

### What happened

CodeRabbit did not auto-review the PR. Its first comment said:

> Review skipped. Auto reviews are disabled on base/target branches other than the default branch.

I had to manually invoke it with `@coderabbitai review`. After that, CodeRabbit produced a high-level walkthrough and a sequence diagram, but no line-level comments or suggestions.

**Finding:** out of the box, CodeRabbit is conservative and requires manual triggering.

---

## 2. Configuring CodeRabbit

I opened a second PR to add a `.coderabbit.yaml` file that enables auto-review on every branch and switches the profile from `chill` to `assertive`.

- **PR:** [#82 — chore(coderabbit): enable assertive auto-review on all branches](https://github.com/AdamTheCreator/spacefit-platform/pull/82)

Initial configuration:

```yaml
language: en-us
reviews:
  profile: assertive
  request_changes: true
  auto_review:
    enabled: true
    base_branches: []
```

### What happened

CodeRabbit immediately found a problem I had not noticed: a parsing error on `language: en-us`. The schema expects `en-US`. The tool was not just reviewing code; it was validating its own configuration.

I pushed a fixup commit changing `en-us` to `en-US`.

**Finding:** CodeRabbit's config is strict, and it self-reports misconfigurations.

---

## 3. Creating a Deliberate Bug to Test the Review

To verify that CodeRabbit catches real issues, I opened a third PR with a small, intentional React bug.

- **PR:** [#83 — test(coderabbit): deliberate useEffect dependency bug](https://github.com/AdamTheCreator/spacefit-platform/pull/83)

The component was a throwaway counter with a stale closure:

```tsx
useEffect(() => {
  const interval = setInterval(() => {
    setCount(count + 1);
  }, 1000);
  return () => clearInterval(interval);
}, []);
```

### What happened

CodeRabbit posted a line-level comment identifying the stale closure. It explained that `count` is captured as `0`, so the interval only increments once, and it recommended using the functional state updater:

```tsx
setCount((currentCount) => currentCount + 1);
```

That is exactly the bug I planted. The review was precise and actionable.

**Finding:** with the assertive profile enabled, CodeRabbit produces concrete, line-level feedback on real bugs.

---

## 4. Operational Lesson: Rate Limits

After a few back-to-back reviews, CodeRabbit hit its per-developer review limit:

> Review limit reached. Next review available in 15 minutes.

The interactive `@coderabbitai` chat step has to wait for the cooldown, or the organization needs usage-based billing enabled.

**Finding:** the free/Pro Plus plan has real rate limits. For a high-volume workflow, you need to plan review cadence or enable usage-based billing.

---

## 5. Progression Summary

| Step | PR | Outcome |
|------|----|---------|
| First real PR | #81 — Traffic counts card | Manual trigger required; summary and diagram, no line comments |
| Config PR | #82 — CodeRabbit config | Auto-review enabled; CodeRabbit found its own config typo |
| Deliberate bug PR | #83 — useEffect stale closure | Line-level comment caught the bug and suggested the fix |
| Interactive fix | Pending on #83 | Rate limit blocks immediate `@coderabbitai` chat |

---

## 6. Takeaways for the Session

1. CodeRabbit is easy to install but needs config tuning to be useful at scale.
2. Its default profile is conservative; assertive mode gives actionable feedback.
3. It validates `.coderabbit.yaml` strictly.
4. It can identify real React bugs like stale closures.
5. Review limits are the main operational constraint in a demo or high-volume workflow.

---

## 7. Recommended Next Steps

For a production rollout, I would:

- Merge the `.coderabbit.yaml` config.
- Enable usage-based reviews if the team is high-volume.
- Add path-specific guides for React/TypeScript conventions so the feedback stays aligned with the codebase.

---

## PR References

- https://github.com/AdamTheCreator/spacefit-platform/pull/81
- https://github.com/AdamTheCreator/spacefit-platform/pull/82
- https://github.com/AdamTheCreator/spacefit-platform/pull/83
