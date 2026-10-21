/**
 * Shared tone metadata for both pages.
 *
 * Values and labels here MUST match contracts/api.md exactly — this is the
 * single source of truth so index.html's tone cards and gallery.html's tone
 * badges/filter chips never drift apart from each other or from the backend.
 */
window.PRODUCTIFY_TONES = [
  {
    value: "vc",
    label: "Silicon Valley Startup",
    emoji: "🚀", // 🚀
    blurb: "Category creation, metrics, disruption talk",
  },
  {
    value: "luxury",
    label: "Luxury Brand",
    emoji: "💎", // 💎
    blurb: "Restraint, invented heritage, price withheld",
  },
  {
    value: "infomercial",
    label: "Late-Night Infomercial",
    emoji: "📺", // 📺
    blurb: "Urgent, shouty, three-easy-payments right now",
  },
  {
    value: "kickstarter",
    label: "Kickstarter Campaign",
    emoji: "🎯", // 🎯
    blurb: "Community-driven, stretch goals, early-bird pricing",
  },
];

window.PRODUCTIFY_TONE_ORDER = window.PRODUCTIFY_TONES.map(function (t) {
  return t.value;
});

window.PRODUCTIFY_TONE_LABELS = {};
window.PRODUCTIFY_TONES.forEach(function (t) {
  window.PRODUCTIFY_TONE_LABELS[t.value] = t.label;
});
