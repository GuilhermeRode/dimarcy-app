// Approximate coordinates for cities in SP/PR/SC/RS — the states this business currently
// sells to. Keyed by normalized "city/uf" (lowercase, accents stripped, trimmed) so lookups
// tolerate the usual data-entry noise (typos, extra spaces, mixed case).
const RAW = {
  "sao paulo/sp": [-23.5505, -46.6333],
  "campinas/sp": [-22.9099, -47.0626],
  "santos/sp": [-23.9608, -46.3336],
  "sorocaba/sp": [-23.5015, -47.4526],
  "ribeirao preto/sp": [-21.1775, -47.8103],
  "sao jose dos campos/sp": [-23.2237, -45.9009],
  "curitiba/pr": [-25.4284, -49.2733],
  "londrina/pr": [-23.3103, -51.1628],
  "maringa/pr": [-23.4205, -51.9331],
  "cascavel/pr": [-24.9578, -53.4595],
  "ponta grossa/pr": [-25.0945, -50.1633],
  "florianopolis/sc": [-27.5954, -48.5480],
  "blumenau/sc": [-26.9194, -49.0661],
  "joinville/sc": [-26.3045, -48.8487],
  "brusque/sc": [-27.0979, -48.9108],
  "chapeco/sc": [-27.1004, -52.6152],
  "criciuma/sc": [-28.6775, -49.3697],
  "itajai/sc": [-26.9078, -48.6614],
  "jaragua do sul/sc": [-26.4869, -49.0679],
  "rio do sul/sc": [-27.2154, -49.6438],
  "lages/sc": [-27.8158, -50.3264],
  "porto alegre/rs": [-30.0346, -51.2177],
  "caxias do sul/rs": [-29.1678, -51.1794],
  "gramado/rs": [-29.3747, -50.8768],
  "bento goncalves/rs": [-29.1712, -51.5185],
  "novo hamburgo/rs": [-29.6783, -51.1306],
  "pelotas/rs": [-31.7654, -52.3376],
  "canoas/rs": [-29.9177, -51.1836],
  "santa maria/rs": [-29.6842, -53.8069],
};

function normalize(city, state) {
  const key = `${(city || "").trim()}/${(state || "").trim()}`
    .toLowerCase()
    .normalize("NFD").replace(/[̀-ͯ]/g, ""); // strip accents
  return key;
}

export function cityCoords(city, state) {
  return RAW[normalize(city, state)] || null;
}
