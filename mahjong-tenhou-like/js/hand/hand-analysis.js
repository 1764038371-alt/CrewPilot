function renderWaitPanel() {
  const panel = $("waitPanel");
  if (!state.waitDisplay) {
    panel.hidden = true;
    return;
  }

  const waits = getVisibleWaits();
  if (waits.length === 0) {
    panel.hidden = true;
    return;
  }

  panel.hidden = false;
  panel.innerHTML = `聴牌 <strong>待ち</strong>: ${waits.map((tile) => tile.mark).join(" / ")}`;
}

function getVisibleWaits() {
  if (isCpuOnlyMode()) return [];
  if (isTenpaiShape("bottom")) return getWaitsForPlayer("bottom");
  if (state.current === "bottom" && state.hands.bottom.length % 3 === 2) {
    const allWaits = new Map();
    state.hands.bottom.forEach((_, index) => {
      const trial = state.hands.bottom.filter((__, tileIndex) => tileIndex !== index);
      getWaitsForPlayer("bottom", trial).forEach((tile) => allWaits.set(tile.index, tile));
    });
    return [...allWaits.values()];
  }
  return [];
}

function getWaits(hand) {
  const counts = countTiles(hand);
  return allTileTypes.filter((tile) => counts[tile.index] < 4 && isWinningHand([...hand, tile]));
}

function getWaitsForPlayer(player, hand = state.hands[player]) {
  const counts = countTiles([...hand, ...getMeldTiles(player)]);
  const requiredMelds = 4 - state.melds[player].length;
  return allTileTypes.filter((tile) => (
    counts[tile.index] < 4 &&
    isWinningHandWithMeldCount([...hand, tile], requiredMelds)
  ));
}

function getYakuWaitsForPlayer(player, hand = state.hands[player], method = "ロン") {
  return getWaitsForPlayer(player, hand).filter((tile) => isValidAgariForHand(player, method, hand, tile));
}

function isTenpai(player) {
  return isTenpaiShape(player) && getWaitsForPlayer(player).length > 0;
}

function isTenpaiShape(player) {
  return state.hands[player].length === baseHandSize(player);
}

function countTiles(tiles) {
  const counts = Array(34).fill(0);
  tiles.forEach((tile) => {
    const index = tile.tileIndex ?? tile.index;
    counts[index] += 1;
  });
  return counts;
}

function isWinningHand(tiles) {
  if (tiles.length % 3 !== 2) return false;
  const counts = countTiles(tiles);
  if (isThirteenOrphans(counts)) return true;
  if (isSevenPairs(counts)) return true;

  for (let index = 0; index < counts.length; index += 1) {
    if (counts[index] < 2) continue;
    const rest = [...counts];
    rest[index] -= 2;
    if (canMakeMelds(rest)) return true;
  }
  return false;
}

function isWinningForPlayer(player, extraTile = null) {
  const tiles = extraTile ? [...state.hands[player], extraTile] : [...state.hands[player]];
  const requiredMelds = 4 - state.melds[player].length;
  if (tiles.length !== requiredMelds * 3 + 2) return false;
  return isWinningHandWithMeldCount(tiles, requiredMelds);
}

function isValidAgariForPlayer(player, method, extraTile = null) {
  if (!isWinningForPlayer(player, extraTile)) return false;
  if (method === "ロン" && typeof hasDeclaredRiichi === "function" && hasDeclaredRiichi(player)) return true;
  const winningTile = extraTile ?? state.hands[player][state.hands[player].length - 1];
  const handTiles = method === "ツモ" ? getAgariHandTiles(player, method) : [...state.hands[player]];
  return isValidAgariForHand(player, method, handTiles, winningTile);
}

function isValidAgariForHand(player, method, handTiles, winningTile) {
  const info = evaluateAgari(player, method, handTiles, winningTile);
  return info.yaku.some((item) => !["ドラ", "赤ドラ", "裏ドラ", "和了形"].includes(item.name));
}

function isWinningHandWithMeldCount(tiles, requiredMelds) {
  const counts = countTiles(tiles);
  if (requiredMelds === 4 && isThirteenOrphans(counts)) return true;
  if (requiredMelds === 4 && isSevenPairs(counts)) return true;

  for (let index = 0; index < counts.length; index += 1) {
    if (counts[index] < 2) continue;
    const rest = [...counts];
    rest[index] -= 2;
    if (canMakeExactMelds(rest, requiredMelds)) return true;
  }
  return false;
}

function canMakeExactMelds(counts, remainingMelds) {
  if (remainingMelds === 0) return counts.every((count) => count === 0);
  const first = counts.findIndex((count) => count > 0);
  if (first === -1) return remainingMelds === 0;

  if (counts[first] >= 3) {
    counts[first] -= 3;
    if (canMakeExactMelds(counts, remainingMelds - 1)) return true;
    counts[first] += 3;
  }

  const suitStart = Math.floor(first / 9) * 9;
  const number = first - suitStart + 1;
  const isSuitTile = first < 27;
  if (isSuitTile && number <= 7 && counts[first + 1] > 0 && counts[first + 2] > 0) {
    counts[first] -= 1;
    counts[first + 1] -= 1;
    counts[first + 2] -= 1;
    if (canMakeExactMelds(counts, remainingMelds - 1)) return true;
    counts[first] += 1;
    counts[first + 1] += 1;
    counts[first + 2] += 1;
  }

  return false;
}

function isThirteenOrphans(counts) {
  const terminals = [0, 8, 9, 17, 18, 26, 27, 28, 29, 30, 31, 32, 33];
  return terminals.every((index) => counts[index] > 0) && terminals.some((index) => counts[index] > 1);
}

function isSevenPairs(counts) {
  return counts.filter((count) => count === 2).length === 7 && counts.every((count) => count === 0 || count === 2);
}

function canMakeMelds(counts) {
  const first = counts.findIndex((count) => count > 0);
  if (first === -1) return true;

  if (counts[first] >= 3) {
    counts[first] -= 3;
    if (canMakeMelds(counts)) return true;
    counts[first] += 3;
  }

  const suitStart = Math.floor(first / 9) * 9;
  const number = first - suitStart + 1;
  const isSuitTile = first < 27;
  if (isSuitTile && number <= 7 && counts[first + 1] > 0 && counts[first + 2] > 0) {
    counts[first] -= 1;
    counts[first + 1] -= 1;
    counts[first + 2] -= 1;
    if (canMakeMelds(counts)) return true;
    counts[first] += 1;
    counts[first + 1] += 1;
    counts[first + 2] += 1;
  }

  return false;
}
