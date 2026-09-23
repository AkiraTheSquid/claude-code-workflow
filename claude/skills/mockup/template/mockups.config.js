/* ------------------------------------------------------------------
   The one place that knows what exists. The index gallery, the bar on
   every variant page, and the screenshot script all read THIS file — so
   a scene that is not listed here does not exist as far as the harness
   is concerned, and a listed scene with no function warns in the console.

   Replace every string below. Keep the shape.
   ------------------------------------------------------------------ */

window.MOCKUPS = {
  title: 'Feature name — front-end slice',
  subtitle: 'Nothing is wired. Every screen is the same file, driven by a scene name.',

  // Phone-width popup that the bar's `phone` button (key: p) opens.
  phone: { width: 420, height: 860 },

  variants: [
    {
      id: 'a',
      file: 'variant-a.html',
      name: 'A · one-line description of this layout',
      status: 'chosen', // chosen | reference | archived | open | '' (omit)
      lede: 'What this layout puts where, and why — two or three sentences, '
        + 'written so it reads as an argument for the layout, not a caption.',
      scenes: [
        { id: 'fresh', name: 'Fresh', note: 'Just opened. Nothing entered yet.' },
        { id: 'working', name: 'Working', note: 'Mid-task, requirements met, primary action live.' },
        { id: 'warning', name: 'Warning', note: 'Under the floor — the number being warned about blinks.' },
        { id: 'empty', name: 'Empty', note: 'Nothing to show. The state that usually gets skipped.' },
      ],
    },
    {
      id: 'b',
      file: 'variant-b.html',
      name: 'B · the alternative — kept for comparison',
      status: 'reference',
      lede: 'How this one differs from A in one paragraph. Same scene ids as A '
        + 'wherever the scene means the same thing, so ] and [ compare like with like.',
      scenes: [
        { id: 'fresh', name: 'Fresh', note: 'Same moment as A · fresh, other layout.' },
        { id: 'working', name: 'Working', note: 'Same moment as A · working.' },
        { id: 'warning', name: 'Warning', note: 'Same moment as A · warning.' },
      ],
    },
  ],

  // Optional: PNGs from earlier passes whose source file no longer exists.
  stills: [],

  // Optional: HTML shown at the bottom of the index. Use it for the decisions
  // the mockup is asking for — the open calls, not a summary of the pictures.
  notes: '<b>Open call.</b> Name the decision you want back, and what changes '
    + 'if the answer goes the other way.',
};
