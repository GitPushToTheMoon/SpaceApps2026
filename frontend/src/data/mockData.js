// ---------------------------------------------------------------------------
// MOCK DATA — placeholder until the FastAPI backend / database is connected.
// The shapes here are the contract the frontend expects from the API.
// ---------------------------------------------------------------------------

export const MOCK_MATERIALS = [
  { key: 'cotton', name: 'Cotton clothing', cat: 'material', flam: 3, soft: true, swap: 'nomexbag' },
  { key: 'towels', name: 'Cotton towels', cat: 'material', flam: 3, soft: true, swap: 'nomexbag' },
  { key: 'manuals', name: 'Paper manuals', cat: 'material', flam: 3, soft: true, swap: 'nomexbag' },
  { key: 'foam', name: 'Polyurethane foam', cat: 'material', flam: 3, swap: 'melamine' },
  { key: 'wipes', name: 'Alcohol wipes', cat: 'material', flam: 3, swap: 'canister' },
  { key: 'pebags', name: 'Polyethylene bags', cat: 'material', flam: 2, swap: 'frfilm' },
  { key: 'velcro', name: 'Hook-and-loop patches', cat: 'material', flam: 2, swap: 'covered' },
  { key: 'food', name: 'Packaged food', cat: 'material', flam: 2 },
  { key: 'pvc', name: 'PVC-insulated wire harness', cat: 'material', flam: 2, swap: 'ptfe' },
  { key: 'lube', name: 'Lubricant oil', cat: 'material', flam: 2 },
  { key: 'ctb', name: 'Cargo transfer bag', cat: 'material', flam: 2, soft: true, swap: 'nomexbag' },
  { key: 'nomexbag', name: 'Nomex-bagged soft goods', cat: 'material', flam: 1 },
  { key: 'melamine', name: 'Melamine foam', cat: 'material', flam: 1 },
  { key: 'canister', name: 'Wipes in sealed canister', cat: 'material', flam: 1 },
  { key: 'frfilm', name: 'Fire-retardant film bags', cat: 'material', flam: 1 },
  { key: 'covered', name: 'Covered hook-and-loop', cat: 'material', flam: 1 },
  { key: 'ptfe', name: 'PTFE-insulated wire harness', cat: 'material', flam: 1 },
  // PSI test dataset entries (ds = dataset metadata)
  { key: 'methanol', name: 'methanol', cat: 'material', flam: 3, ds: { plain: 'Liquid fuel droplet', state: 'liquid', tests: 157 } },
  { key: 'heptane', name: 'heptane', cat: 'material', flam: 3, ds: { plain: 'Liquid fuel droplet', state: 'liquid', tests: 117 } },
  { key: 'pmma', name: 'PMMA', cat: 'material', flam: 3, ds: { plain: 'Acrylic plastic', state: 'solid', tests: 27 } },
  { key: 'ethylene', name: 'ethylene', cat: 'material', flam: 3, ds: { plain: 'Gas fuel', state: 'gas', tests: 22 } },
  { key: 'sibal', name: 'SIBAL fabric', cat: 'material', flam: 2, ds: { plain: '75% cotton / 25% fiberglass cloth', state: 'solid', tests: 6 } },
  { key: 'methane', name: 'methane', cat: 'material', flam: 3, ds: { plain: 'Gas fuel', state: 'gas', tests: 5 } },
  { key: 'silicone', name: 'silicone', cat: 'material', flam: 1, ds: { plain: 'Silicone sheet', state: 'solid', tests: 4 } },
  { key: 'nomex', name: 'Nomex', cat: 'material', flam: 1, ds: { plain: 'Fire-resistant fabric (crew clothing)', state: 'solid', tests: 1 } },
  { key: 'cottonfab', name: 'cotton fabric', cat: 'material', flam: 3, ds: { plain: 'Cotton jersey', state: 'solid', tests: 0 } },
  { key: 'ultem', name: 'Ultem', cat: 'material', flam: 1, ds: { plain: 'High-performance plastic', state: 'solid', tests: 0 } },
  { key: 'waxfg', name: 'wax-fiberglass', cat: 'material', flam: 3, ds: { plain: 'Wax-soaked fiberglass fabric', state: 'solid', tests: 0 } },
  { key: 'hepiso', name: 'heptane-isooctane', cat: 'material', flam: 3, ds: { plain: '50/50 fuel mix (gasoline stand-in)', state: 'liquid', tests: 0 } },
  // Machinery
  { key: 'liion', name: 'Li-ion battery pack', cat: 'machinery', ign: true, heat: 25, liion: true, swap: 'liionbag' },
  { key: 'liionbag', name: 'Li-ion battery pack (bagged)', cat: 'machinery', ign: true, heat: 25, liion: true, bagged: true },
  { key: 'laptop', name: 'Laptop', cat: 'machinery', ign: true, heat: 10 },
  { key: 'warmer', name: 'Food warmer', cat: 'machinery', ign: true, heat: 30 },
  { key: 'printer', name: '3D printer', cat: 'machinery', ign: true, heat: 30 },
  { key: 'exercise', name: 'Motorised exercise device', cat: 'machinery', ign: true, heat: 15 },
  { key: 'fan', name: 'Air circulation fan', cat: 'machinery', ign: true, heat: 5 },
  { key: 'pump', name: 'Propellant pump controller', cat: 'machinery', ign: true, heat: 20 },
  { key: 'consoles', name: 'Flight control consoles', cat: 'machinery', ign: true, heat: 15 },
  { key: 'oxygen', name: 'Oxygen supply', cat: 'machinery', oxy: true },
  // Safety
  { key: 'ext', name: 'Portable extinguisher', cat: 'safety' },
  { key: 'det', name: 'Smoke detector', cat: 'safety' },
  { key: 'mask', name: 'Emergency breathing mask', cat: 'safety' },
];

// Small helpers to keep the seed layouts readable.
const it = (lib, qty, l, w, h) => ({ lib, qty, l, w, h });
const room = (name, type, x, y, items = []) => ({ name, type, x, y, items });

// Functions so each load returns fresh objects (ids get assigned by Room/Item).
export const MOCK_LAYOUTS = {
  iss: () => [
    room('PMM Stowage & Logistics', 'STO', 1, 0, [it('ctb', 1, 50, 42, 25), it('cotton', 2, 30, 20, 5), it('det', 1, 10, 10, 5)]),
    room('Quest Airlock', 'AL', 0, 1, [it('oxygen', 1, 60, 30, 30), it('foam', 1, 40, 30, 4)]),
    room('Node 1 Galley', 'GAL', 1, 1, [it('warmer', 1, 40, 30, 25), it('food', 6, 20, 15, 8), it('wipes', 4, 15, 10, 6), it('ext', 1, 50, 15, 15)]),
    room('Destiny Lab', 'LAB', 2, 1, [it('printer', 1, 45, 45, 40), it('pmma', 3, 10, 8, 4), it('laptop', 2, 35, 25, 3), it('ext', 1, 50, 15, 15), it('det', 1, 10, 10, 5)]),
    room('Node 2 Crew Quarters', 'CQ', 3, 1, [it('nomexbag', 4, 30, 20, 5), it('laptop', 1, 35, 25, 3), it('liion', 1, 20, 10, 8), it('det', 1, 10, 10, 5)]),
    room('Node 3 Hygiene & Exercise', 'HYG', 1, 2, [it('exercise', 1, 120, 60, 50), it('towels', 2, 40, 30, 1)]),
    room('Columbus Lab', 'LAB', 3, 2, [it('ptfe', 3, 100, 5, 5), it('laptop', 1, 35, 25, 3), it('det', 1, 10, 10, 5)]),
  ],
  transit: () => [
    room('Engine room', 'ENG', 0, 1, [it('pump', 1, 40, 30, 20), it('lube', 2, 10, 10, 20)]),
    room('Spine A', 'HALL', 1, 1, [it('ctb', 1, 50, 42, 25)]),
    room('Spine B', 'HALL', 2, 1),
    room('Spine C', 'HALL', 3, 1),
    room('Spine D', 'HALL', 4, 1),
    room('Operations', 'OPS', 5, 1, [it('consoles', 2, 80, 40, 30), it('manuals', 3, 30, 22, 2), it('det', 1, 10, 10, 5)]),
    room('Galley', 'GAL', 1, 0, [it('warmer', 1, 40, 30, 25), it('food', 6, 20, 15, 8), it('ext', 1, 50, 15, 15)]),
    room('Crew quarters', 'CQ', 1, 2, [it('cotton', 3, 30, 20, 5), it('liion', 1, 20, 10, 8)]),
    room('Lab', 'LAB', 2, 0, [it('printer', 1, 45, 45, 40), it('pmma', 2, 10, 8, 4)]),
    room('Airlock', 'AL', 2, 2, [it('oxygen', 1, 60, 30, 30)]),
    room('Power bay', 'PWR', 3, 0, [it('liion', 2, 20, 10, 8), it('pvc', 2, 100, 5, 5)]),
    room('Hygiene', 'HYG', 3, 2, [it('towels', 2, 40, 30, 1)]),
    room('Stowage', 'STO', 4, 0, [it('ctb', 2, 50, 42, 25), it('foam', 1, 40, 30, 5)]),
    room('Life support', 'LS', 4, 2, [it('oxygen', 1, 60, 30, 30), it('fan', 2, 20, 20, 10)]),
  ],
  blank: () => [],
};
