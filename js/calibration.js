// Maps real-world [lon, lat] onto pixel positions of the hand-drawn map image.
//
// The artwork is not a true projection, so instead of a fixed formula we use
// landmark pairs (a known coastline point and where the artist drew it) and
// bend a smooth surface through them (thin-plate spline). To improve the fit
// somewhere, add or nudge a landmark: [lon, lat, imageX, imageY].
// Turn on the debug outline with ?debug in the URL to see the result.

export const MAP_IMAGE = { src: "assets/world-map.webp", width: 1774, height: 887 };

export const LANDMARKS = [
  // Europe / North Atlantic
  [-19.0, 65.0, 735, 180],   // Iceland
  [-10.0, 53.3, 765, 257],   // Ireland, west coast
  [-9.3, 38.7, 765, 345],    // Lisbon
  [-5.6, 36.0, 795, 352],    // Gibraltar
  [10.6, 57.7, 910, 225],    // Skagen, Denmark
  [14.0, 37.5, 910, 387],    // Sicily
  [22.0, 36.6, 940, 372],    // Peloponnese
  [25.8, 71.0, 995, 140],    // North Cape
  [29.0, 41.1, 980, 335],    // Bosporus
  [33.0, 35.0, 1000, 372],   // Cyprus
  [37.0, 65.5, 1017, 170],   // White Sea
  [-43.9, 59.8, 591, 220],   // Cape Farewell, Greenland

  // North America
  [-166.0, 64.5, 92, 162],   // Seward Peninsula
  [-156.8, 71.3, 140, 126],  // Point Barrow
  [-141.0, 69.6, 222, 140],  // Alaska / Yukon border, Arctic coast
  [-123.0, 49.0, 235, 272],  // 49th parallel, Pacific end
  [-95.0, 49.0, 380, 272],   // Lake of the Woods
  [-80.0, 51.3, 452, 262],   // James Bay
  [-80.4, 25.2, 428, 402],   // Florida tip
  [-117.1, 32.5, 250, 360],  // San Diego
  [-63.5, 44.7, 530, 295],   // Halifax
  [-52.7, 47.5, 562, 282],   // Newfoundland
  [-155.5, 19.6, 137, 410],  // Hawaii
  [-85.0, 22.0, 410, 418],   // Western Cuba
  [-87.5, 21.0, 390, 430],   // Yucatán

  // South America
  [-79.5, 9.0, 415, 487],    // Panama
  [-74.8, 11.0, 450, 472],   // Barranquilla
  [-81.3, -4.7, 407, 555],   // Punta Pariñas
  [-71.6, -33.0, 440, 720],  // Valparaíso
  [-67.5, -55.5, 480, 825],  // Cape Horn
  [-34.8, -7.1, 652, 567],   // Cabo Branco
  [-43.2, -22.9, 605, 640],  // Rio de Janeiro
  [-59.0, -51.7, 525, 800],  // Falklands
  [-90.5, -0.5, 375, 540],   // Galápagos

  // Africa
  [-17.4, 14.7, 722, 482],   // Dakar
  [-7.7, 4.4, 765, 525],     // Cape Palmas
  [9.5, 4.0, 855, 530],      // Bight of Biafra
  [8.7, -0.7, 855, 550],     // Cape Lopez
  [20.0, -34.8, 910, 740],   // Cape Agulhas
  [32.6, -26.0, 975, 690],   // Maputo
  [39.7, -4.0, 1035, 575],   // Mombasa
  [51.3, 10.4, 1075, 512],   // Horn of Africa
  [43.4, 12.6, 1047, 485],   // Bab-el-Mandeb
  [46.5, -25.5, 1055, 677],  // Madagascar, south
  [49.3, -12.0, 1080, 602],  // Madagascar, north

  // Asia
  [56.3, 26.5, 1122, 415],   // Strait of Hormuz
  [51.2, 25.6, 1105, 422],   // Qatar
  [59.8, 22.5, 1145, 432],   // Ras al Hadd
  [69.5, 21.5, 1182, 435],   // Kathiawar
  [77.5, 8.1, 1213, 501],    // Southern tip of India
  [88.5, 22.0, 1272, 440],   // Ganges delta
  [100.5, 13.5, 1340, 480],  // Bangkok
  [105.0, 8.7, 1360, 508],   // Cà Mau
  [109.7, 19.2, 1392, 455],  // Hainan
  [121.9, 31.0, 1450, 387],  // Shanghai
  [121.0, 23.7, 1450, 427],  // Taiwan
  [121.0, 18.5, 1452, 450],  // Northern Luzon
  [125.5, 6.0, 1475, 515],   // Mindanao
  [103.8, 1.3, 1340, 547],   // Singapore
  [95.3, 5.6, 1292, 522],    // Northern Sumatra
  [105.8, -5.9, 1350, 577],  // Sunda Strait
  [114.5, -8.3, 1410, 587],  // Eastern Java
  [129.0, 35.0, 1477, 372],  // Busan
  [139.7, 35.7, 1525, 370],  // Tokyo
  [143.0, 43.5, 1545, 320],  // Hokkaido
  [142.8, 50.0, 1540, 285],  // Sakhalin
  [156.7, 51.0, 1598, 277],  // Kamchatka, southern tip
  [155.5, 56.0, 1590, 233],  // Kamchatka, west coast
  [162.5, 56.0, 1617, 233],  // Kamchatka, east coast
  [161.0, 60.5, 1608, 200],  // Penzhina Bay
  [150.8, 59.5, 1575, 222],  // Magadan
  [142.7, 54.4, 1530, 250],  // Northern Sakhalin
  [190.0, 66.0, 1695, 175],  // Chukotka (lon past 180)
  [126.0, 73.0, 1460, 125],  // Lena delta
  [100.0, 76.0, 1290, 115],  // Taymyr
  [70.0, 70.0, 1190, 120],   // Yamal
  [108.0, 53.3, 1375, 258],  // Lake Baikal
  [69.0, 55.4, 1175, 250],   // Northern Kazakhstan border

  // Oceania
  [142.5, -10.7, 1565, 592], // Cape York
  [131.0, -12.4, 1505, 597], // Darwin
  [113.2, -26.0, 1397, 677], // Steep Point
  [115.0, -34.4, 1410, 730], // Cape Leeuwin
  [153.6, -28.6, 1622, 685], // Byron Bay
  [146.4, -39.1, 1585, 760], // Wilsons Promontory
  [146.8, -43.6, 1575, 792], // Southern Tasmania
  [172.7, -34.4, 1700, 710], // Cape Reinga
  [168.3, -46.6, 1665, 797], // Bluff
  [150.5, -10.5, 1615, 590], // Eastern Papua New Guinea
  [131.0, -1.0, 1502, 542],  // Vogelkop
];

// Smoothing: 0 passes exactly through every landmark; larger values trade
// accuracy at the landmarks for a calmer surface between them.
const SMOOTHING = 20;

function kernel(r2) {
  return r2 === 0 ? 0 : r2 * Math.log(r2);
}

function solve(A, b) {
  const n = b.length;
  const M = A.map((row, i) => [...row, b[i]]);
  for (let c = 0; c < n; c++) {
    let p = c;
    for (let r = c + 1; r < n; r++) if (Math.abs(M[r][c]) > Math.abs(M[p][c])) p = r;
    [M[c], M[p]] = [M[p], M[c]];
    for (let r = c + 1; r < n; r++) {
      const f = M[r][c] / M[c][c];
      for (let k = c; k <= n; k++) M[r][k] -= f * M[c][k];
    }
  }
  const x = new Array(n).fill(0);
  for (let r = n - 1; r >= 0; r--) {
    let s = M[r][n];
    for (let k = r + 1; k < n; k++) s -= M[r][k] * x[k];
    x[r] = s / M[r][r];
  }
  return x;
}

// Also used to place markers on country minimaps from their own landmarks.
export function fitSpline(points, smoothing = SMOOTHING) {
  const n = points.length;
  const size = n + 3;
  const A = Array.from({ length: size }, () => new Array(size).fill(0));
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      const dx = points[i][0] - points[j][0];
      const dy = points[i][1] - points[j][1];
      A[i][j] = kernel(dx * dx + dy * dy) + (i === j ? smoothing : 0);
    }
    A[i][n] = A[n][i] = 1;
    A[i][n + 1] = A[n + 1][i] = points[i][0];
    A[i][n + 2] = A[n + 2][i] = points[i][1];
  }
  const zeros = [0, 0, 0];
  const wx = solve(A, [...points.map((p) => p[2]), ...zeros]);
  const wy = solve(A, [...points.map((p) => p[3]), ...zeros]);

  return function (lon, lat) {
    let x = wx[n] + wx[n + 1] * lon + wx[n + 2] * lat;
    let y = wy[n] + wy[n + 1] * lon + wy[n + 2] * lat;
    for (let i = 0; i < n; i++) {
      const dx = lon - points[i][0];
      const dy = lat - points[i][1];
      const u = kernel(dx * dx + dy * dy);
      x += wx[i] * u;
      y += wy[i] * u;
    }
    return [x, y];
  };
}

export const toImage = fitSpline(LANDMARKS, SMOOTHING);

// The artwork splits the Pacific at the Bering Strait: Chukotka sits on the
// far right, the Aleutians on the far left.
// Other countries that straddle the 180th meridian (Fiji, Kiribati...) are
// kept in one piece on the Asian side.
export function wrapLongitude(lon, countryName, spansDateline = false) {
  if (countryName === "United States of America") return lon > 0 ? lon - 360 : lon;
  if ((countryName === "Russia" || spansDateline) && lon < 0) return lon + 360;
  return lon;
}

export function spansDateline(feature) {
  let east = false;
  let west = false;
  const visit = (c) => {
    if (typeof c[0] === "number") {
      if (c[0] > 170) east = true;
      if (c[0] < -170) west = true;
    } else c.forEach(visit);
  };
  visit(feature.geometry.coordinates);
  return east && west;
}
