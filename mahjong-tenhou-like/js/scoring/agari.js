function declareRon() {
  if (!canRon()) return;
  const pending = getBottomRonTarget();
  const tile = pending.tile;
  const discarder = pending.discarder;
  showAgari("bottom", "ロン", tile, discarder);
}

function declareTsumo() {
  if (!canTsumo()) return;
  showAgari("bottom", "ツモ", state.hands.bottom[state.hands.bottom.length - 1]);
}

function showAgari(winner, method, tile, discarder = null) {
  if (state.roundEnded) return;
  state.roundEnded = true;
  state.lastWinner = winner;
  state.current = "ended";
  state.callChoices = [];
  state.ronPending = false;
  state.pendingRon = null;

  const handTiles = getAgariHandTiles(winner, method);
  const agariInfo = evaluateAgari(winner, method, handTiles, tile);
  const payments = agariInfo.payments;
  const scoreBefore = { ...state.scores };
  if (method === "ロン" && discarder) {
    state.scores[winner] += payments.ron;
    state.scores[discarder] -= payments.ron;
  } else {
    players.filter((player) => player !== winner).forEach((player) => {
      const payment = agariInfo.isDealer ? payments.tsumoAll : player === players[state.dealerIndex] ? payments.tsumoDealer : payments.tsumoChild;
      state.scores[player] -= payment;
      state.scores[winner] += payment;
    });
  }
  const riichiPot = state.riichiSticks * 1000;
  state.scores[winner] += riichiPot;
  state.riichiSticks = 0;
  learnFromRoundResult(scoreBefore, { winner, discarder, method });

  $("nextRoundButton").textContent = "次局へ";
  $("resultTitle").textContent = `${method} 和了`;
  $("resultDetail").textContent = `${playerName(winner)} / 和了牌 ${tile.mark}`;
  renderAgariHand(handTiles, tile, winner);
  $("resultYaku").innerHTML = [
    ...agariInfo.yaku.map((item) => `<div>${item.name} ${item.han}飜</div>`),
    agariInfo.uraDoraIndicator ? `<div>裏ドラ表示牌 ${agariInfo.uraDoraIndicator.mark} / 裏ドラ ${getDoraTileType(agariInfo.uraDoraIndicator).mark}</div>` : "",
    `<div>${agariInfo.han}飜 ${agariInfo.fu}符 ${agariInfo.pointText}</div>`,
    riichiPot > 0 ? `<div>供託 +${riichiPot}点</div>` : "",
  ].join("");
  $("resultScores").innerHTML = players
    .map((player) => {
      const delta = state.scores[player] - scoreBefore[player];
      const deltaText = delta === 0 ? "" : `<span class="${delta > 0 ? "score-plus" : "score-minus"}">${delta > 0 ? "+" : ""}${delta}</span>`;
      return `<div>${playerName(player)} ${state.scores[player]} ${deltaText}</div>`;
    })
    .join("");
  log(`${playerName(winner)} ${method} ${tile.mark}`);
  finishPaifuRound({
    type: "agari",
    winner,
    winnerName: playerName(winner),
    method,
    tile: compactTile(tile),
    yaku: agariInfo.yaku,
    han: agariInfo.han,
    fu: agariInfo.fu,
    pointText: agariInfo.pointText,
    scores: { ...state.scores },
  });
  if (isCpuOnlyMode()) {
    $("scoreOverlay").hidden = true;
    render();
    scheduleCpu(() => {
      if (state.paused) {
        state.resumeAction = advanceAfterAgari;
        return;
      }
      advanceAfterAgari();
    }, cpuAutoAdvanceMs);
    return;
  }
  $("scoreOverlay").hidden = false;
  render();
}

function getAgariHandTiles(winner, method) {
  const tiles = [...state.hands[winner]];
  if (method === "ツモ" && tiles.length % 3 === 2) {
    return tiles.slice(0, -1);
  }
  return tiles;
}

function renderAgariHand(handTiles, winningTile, winner = "bottom") {
  const container = $("resultHand");
  container.innerHTML = "";
  handTiles.forEach((tile) => container.appendChild(createTile(tile)));
  const agariTile = createTile(winningTile);
  agariTile.classList.add("winning-tile");
  container.appendChild(agariTile);
  [...state.melds[winner]].reverse().forEach((meld) => {
    const meldElement = document.createElement("div");
    meldElement.className = `meld result-meld from-${meld.fromPlayer}`;
    meld.tiles.forEach((tile, index) => {
      const element = createTile(tile);
      if (index === meld.claimedIndex) element.classList.add("claimed");
      meldElement.appendChild(element);
    });
    container.appendChild(meldElement);
  });
}

function hasDeclaredRiichi(player) {
  return Boolean(state.riichiPlayers[player] || state.rivers[player]?.some((entry) => entry.sideways));
}

function evaluateAgari(winner, method, handTiles, winningTile) {
  const closedTiles = [...handTiles, winningTile];
  const completeTiles = [...closedTiles, ...getMeldTiles(winner)];
  const counts = countTiles(completeTiles);
  const context = {
    winner,
    method,
    winningTile,
    menzen: state.melds[winner].length === 0,
    seat: seatWind(winner),
    round: roundWind(),
  };
  const handShape = analyzeHandShape(closedTiles, winner, context);
  const yaku = evaluateYaku(completeTiles, counts, handShape, context);
  const doraCount = countDora(completeTiles);
  const redDoraCount = countRedDora(completeTiles);
  const riichiDeclared = hasDeclaredRiichi(winner);
  const uraDoraCount = riichiDeclared ? countUraDora(completeTiles) : 0;
  if (doraCount > 0) yaku.push({ name: "ドラ", han: doraCount });
  if (redDoraCount > 0) yaku.push({ name: "赤ドラ", han: redDoraCount });
  if (uraDoraCount > 0) yaku.push({ name: "裏ドラ", han: uraDoraCount });

  const han = yaku.reduce((sum, item) => sum + item.han, 0);
  const fu = calculateFu(counts, handShape, context);
  const isDealer = winner === players[state.dealerIndex];
  const payments = getAgariPayments(han, fu, isDealer);
  return {
    yaku,
    han,
    fu,
    isDealer,
    payments,
    uraDoraCount,
    uraDoraIndicator: riichiDeclared ? state.uraDoraIndicator : null,
    pointText: method === "ツモ" ? formatTsumoPoints(payments.base, isDealer) : `${payments.base.ron}点`,
  };
}

function analyzeHandShape(closedTiles, winner, context) {
  const counts = countTiles(closedTiles);
  const openMelds = state.melds[winner].map((meld) => ({
    type: meld.type === "チー" ? "sequence" : "triplet",
    open: true,
    tiles: meld.tiles,
    index: meld.type === "チー" ? Math.min(...meld.tiles.map((tile) => tile.tileIndex)) : meld.tiles[0].tileIndex,
  }));

  if (state.melds[winner].length === 0 && isThirteenOrphans(counts)) {
    return { type: "kokushi", melds: [], pair: null, openMelds };
  }
  if (state.melds[winner].length === 0 && isSevenPairs(counts)) {
    return { type: "chiitoi", melds: [], pair: null, openMelds };
  }

  const requiredMelds = 4 - state.melds[winner].length;
  const decompositions = [];
  for (let index = 0; index < counts.length; index += 1) {
    if (counts[index] < 2) continue;
    const rest = [...counts];
    rest[index] -= 2;
    collectMeldDecompositions(rest, requiredMelds, [], decompositions, index);
  }
  const standard = chooseBestDecomposition(decompositions, openMelds, context);
  return {
    type: "standard",
    melds: [...(standard?.melds ?? []), ...openMelds],
    pair: standard?.pair ?? null,
    waitType: standard?.waitType ?? "unknown",
    openMelds,
  };
}

function collectMeldDecompositions(counts, remaining, melds, results, pair) {
  if (remaining === 0) {
    if (counts.every((count) => count === 0)) results.push({ pair, melds: [...melds] });
    return;
  }
  const first = counts.findIndex((count) => count > 0);
  if (first === -1) return;

  if (counts[first] >= 3) {
    counts[first] -= 3;
    collectMeldDecompositions(counts, remaining - 1, [...melds, { type: "triplet", open: false, index: first }], results, pair);
    counts[first] += 3;
  }

  const suitStart = Math.floor(first / 9) * 9;
  const number = first - suitStart + 1;
  if (first < 27 && number <= 7 && counts[first + 1] > 0 && counts[first + 2] > 0) {
    counts[first] -= 1;
    counts[first + 1] -= 1;
    counts[first + 2] -= 1;
    collectMeldDecompositions(counts, remaining - 1, [...melds, { type: "sequence", open: false, index: first }], results, pair);
    counts[first] += 1;
    counts[first + 1] += 1;
    counts[first + 2] += 1;
  }
}

function chooseBestDecomposition(decompositions, openMelds, context) {
  if (decompositions.length === 0) return null;
  return decompositions
    .map((shape) => {
      const melds = [...shape.melds, ...openMelds];
      const waitType = getWaitTypeForShape(shape, context);
      const score =
        (isPinfuShape(melds, shape.pair, { ...context, waitType }) ? 8 : 0) +
        countIipeiko(shape.melds) * 4 +
        (isSanshoku(melds) ? 3 : 0) +
        (isIttsu(melds) ? 3 : 0) -
        melds.filter((meld) => meld.type === "triplet").length;
      return { ...shape, waitType, score };
    })
    .sort((a, b) => b.score - a.score)[0];
}

function evaluateYaku(tiles, counts, shape, context) {
  const yaku = [];
  const yakuman = evaluateYakuman(tiles, counts, shape, context);
  if (yakuman.length > 0) return yakuman;

  const riichiDeclared = hasDeclaredRiichi(context.winner);
  if (context.menzen && riichiDeclared) yaku.push({ name: "立直", han: 1 });
  if (context.menzen && riichiDeclared && state.ippatsuEligible[context.winner]) yaku.push({ name: "一発", han: 1 });
  if (context.menzen && context.method === "ツモ") yaku.push({ name: "門前清自摸和", han: 1 });
  if (context.method === "ツモ" && state.wall.length === 14) yaku.push({ name: "海底摸月", han: 1 });
  if (context.method === "ロン" && state.wall.length === 14) yaku.push({ name: "河底撈魚", han: 1 });
  if (isTanyao(tiles)) yaku.push({ name: "断么九", han: 1 });
  if (shape.type === "chiitoi") yaku.push({ name: "七対子", han: 2 });

  if (shape.type === "standard") {
    if (context.menzen && isPinfuShape(shape.melds, shape.pair, { ...context, waitType: shape.waitType })) yaku.push({ name: "平和", han: 1 });
    const iipeiko = context.menzen ? countIipeiko(shape.melds.filter((meld) => !meld.open)) : 0;
    if (iipeiko >= 2) yaku.push({ name: "二盃口", han: 3 });
    else if (iipeiko === 1) yaku.push({ name: "一盃口", han: 1 });
    const yakuhai = countYakuhaiMelds(shape.melds, context);
    if (yakuhai > 0) yaku.push({ name: "役牌", han: yakuhai });
    if (shape.melds.every((meld) => meld.type === "triplet")) yaku.push({ name: "対々和", han: 2 });
    if (countClosedTriplets(shape.melds, context) >= 3) yaku.push({ name: "三暗刻", han: 2 });
    if (isSanshokuDoukou(shape.melds)) yaku.push({ name: "三色同刻", han: 2 });
    if (isSanshoku(shape.melds)) yaku.push({ name: "三色同順", han: context.menzen ? 2 : 1 });
    if (isIttsu(shape.melds)) yaku.push({ name: "一気通貫", han: context.menzen ? 2 : 1 });
    if (isJunchan(tiles, shape.melds, shape.pair)) yaku.push({ name: "純全帯么九", han: context.menzen ? 3 : 2 });
    if (isChanta(tiles, shape.melds, shape.pair)) yaku.push({ name: "混全帯么九", han: context.menzen ? 2 : 1 });
    if (isShousangen(shape.melds, shape.pair)) yaku.push({ name: "小三元", han: 2 });
  }

  if (isHonroutou(tiles)) yaku.push({ name: "混老頭", han: 2 });
  const flush = getFlushYaku(tiles, context.menzen);
  if (flush) yaku.push(flush);
  if (yaku.length === 0) yaku.push({ name: "和了形", han: 1 });
  return yaku;
}

function evaluateYakuman(tiles, counts, shape, context) {
  const yaku = [];
  if (isThirteenOrphans(counts)) yaku.push({ name: "国士無双", han: 13 });
  if (shape.type === "standard") {
    if (countClosedTriplets(shape.melds, context) === 4) yaku.push({ name: "四暗刻", han: 13 });
    const dragonTriplets = shape.melds.filter((meld) => meld.type === "triplet" && [31, 32, 33].includes(meld.index)).length;
    if (dragonTriplets === 3) yaku.push({ name: "大三元", han: 13 });
    const windTriplets = shape.melds.filter((meld) => meld.type === "triplet" && [27, 28, 29, 30].includes(meld.index)).length;
    if (windTriplets === 3 && [27, 28, 29, 30].includes(shape.pair)) yaku.push({ name: "小四喜", han: 13 });
    if (windTriplets === 4) yaku.push({ name: "大四喜", han: 13 });
  }
  if (tiles.every((tile) => tile.suit === "z")) yaku.push({ name: "字一色", han: 13 });
  if (tiles.every((tile) => (tile.suit === "s" && [2, 3, 4, 6, 8].includes(tile.number)) || tile.tileIndex === 32)) yaku.push({ name: "緑一色", han: 13 });
  if (tiles.every((tile) => tile.suit !== "z" && [1, 9].includes(tile.number))) yaku.push({ name: "清老頭", han: 13 });
  if (isChuurenPoutou(tiles)) yaku.push({ name: "九蓮宝燈", han: 13 });
  return yaku;
}

function calculateFu(counts, shape, context) {
  if (shape.type === "chiitoi") return 25;
  if (shape.type === "kokushi") return 0;
  if (shape.type !== "standard") return context.method === "ツモ" ? 30 : 40;

  const pinfu = isPinfuShape(shape.melds, shape.pair, { ...context, waitType: shape.waitType });
  if (pinfu && context.method === "ツモ") return 20;

  let fu = 20;
  if (context.menzen && context.method === "ロン") fu += 10;
  if (context.method === "ツモ" && !pinfu) fu += 2;
  if (isValuedPair(shape.pair, context)) fu += 2;
  if (["kanchan", "penchan", "tanki"].includes(shape.waitType)) fu += 2;

  shape.melds.forEach((meld) => {
    if (meld.type !== "triplet") return;
    const terminalHonor = isTerminalOrHonorIndex(meld.index);
    const base = terminalHonor ? 8 : 4;
    const wonByRonOnTriplet = context.method === "ロン" && meld.index === context.winningTile.tileIndex;
    fu += meld.open || wonByRonOnTriplet ? base / 2 : base;
  });

  if (fu === 20) fu = 30;
  return Math.ceil(fu / 10) * 10;
}

function isPinfuShape(melds, pair, context = { seat: "", round: "", waitType: "unknown" }) {
  return pair !== null && context.waitType === "ryanmen" && !isValuedPair(pair, context) && melds.every((meld) => meld.type === "sequence");
}

function getWaitTypeForShape(shape, context) {
  const winningIndex = context?.winningTile?.tileIndex;
  if (winningIndex === undefined) return "unknown";
  if (shape.pair === winningIndex) return "tanki";

  const waitTypes = shape.melds
    .filter((meld) => !meld.open && meldContainsWinningTile(meld, winningIndex))
    .map((meld) => waitTypeForMeld(meld, winningIndex));

  if (waitTypes.includes("ryanmen")) return "ryanmen";
  if (waitTypes.includes("kanchan")) return "kanchan";
  if (waitTypes.includes("penchan")) return "penchan";
  if (waitTypes.includes("shanpon")) return "shanpon";
  return "unknown";
}

function meldContainsWinningTile(meld, winningIndex) {
  if (meld.type === "triplet") return meld.index === winningIndex;
  return meld.type === "sequence" && winningIndex >= meld.index && winningIndex <= meld.index + 2;
}

function waitTypeForMeld(meld, winningIndex) {
  if (meld.type === "triplet") return "shanpon";
  const position = winningIndex - meld.index;
  const startNumber = (meld.index % 9) + 1;
  if (position === 1) return "kanchan";
  if (position === 0) return startNumber === 7 ? "penchan" : "ryanmen";
  if (position === 2) return startNumber === 1 ? "penchan" : "ryanmen";
  return "unknown";
}

function countIipeiko(melds) {
  const sequenceKeys = melds
    .filter((meld) => meld.type === "sequence")
    .map((meld) => meld.index)
    .sort((a, b) => a - b);
  let pairs = 0;
  for (let index = 0; index < sequenceKeys.length - 1; index += 1) {
    if (sequenceKeys[index] === sequenceKeys[index + 1]) {
      pairs += 1;
      index += 1;
    }
  }
  return pairs;
}

function countYakuhaiMelds(melds, context) {
  return melds.filter((meld) => meld.type === "triplet" && isValuedPair(meld.index, context)).length;
}

function countClosedTriplets(melds, context) {
  return melds.filter((meld) => isClosedTripletForYaku(meld, context)).length;
}

function isClosedTripletForYaku(meld, context) {
  if (meld.type !== "triplet" || meld.open) return false;
  const winningIndex = context?.winningTile?.tileIndex;
  const wonByRonOnTriplet = context?.method === "ロン" && meld.index === winningIndex;
  return !wonByRonOnTriplet;
}

function isSanshoku(melds) {
  for (let number = 1; number <= 7; number += 1) {
    const suitsFound = new Set(
      melds
        .filter((meld) => meld.type === "sequence" && meld.index % 9 === number - 1)
        .map((meld) => Math.floor(meld.index / 9)),
    );
    if (suitsFound.has(0) && suitsFound.has(1) && suitsFound.has(2)) return true;
  }
  return false;
}

function isSanshokuDoukou(melds) {
  for (let number = 1; number <= 9; number += 1) {
    const indexes = [number - 1, 9 + number - 1, 18 + number - 1];
    if (indexes.every((index) => melds.some((meld) => meld.type === "triplet" && meld.index === index))) return true;
  }
  return false;
}

function isIttsu(melds) {
  for (let suit = 0; suit < 3; suit += 1) {
    const start = suit * 9;
    const sequences = new Set(melds.filter((meld) => meld.type === "sequence").map((meld) => meld.index));
    if (sequences.has(start) && sequences.has(start + 3) && sequences.has(start + 6)) return true;
  }
  return false;
}

function isChanta(tiles, melds, pair) {
  if (!tiles.some((tile) => tile.suit === "z")) return false;
  if (pair !== null && !isTerminalOrHonorIndex(pair)) return false;
  return melds.every((meld) => {
    if (meld.type === "triplet") return isTerminalOrHonorIndex(meld.index);
    return meld.index % 9 === 0 || meld.index % 9 === 6;
  });
}

function isJunchan(tiles, melds, pair) {
  if (tiles.some((tile) => tile.suit === "z")) return false;
  if (pair !== null && !isTerminalOrHonorIndex(pair)) return false;
  return melds.every((meld) => {
    if (meld.type === "triplet") return isTerminalOrHonorIndex(meld.index);
    return meld.index % 9 === 0 || meld.index % 9 === 6;
  });
}

function isShousangen(melds, pair) {
  const dragonTriplets = melds.filter((meld) => meld.type === "triplet" && [31, 32, 33].includes(meld.index)).length;
  return dragonTriplets === 2 && [31, 32, 33].includes(pair);
}

function isHonroutou(tiles) {
  return tiles.every((tile) => tile.suit === "z" || tile.number === 1 || tile.number === 9);
}

function getFlushYaku(tiles, menzen) {
  const suitsFound = new Set(tiles.filter((tile) => tile.suit !== "z").map((tile) => tile.suit));
  if (suitsFound.size !== 1) return null;
  const hasHonor = tiles.some((tile) => tile.suit === "z");
  if (hasHonor) return { name: "混一色", han: menzen ? 3 : 2 };
  return { name: "清一色", han: menzen ? 6 : 5 };
}

function isChuurenPoutou(tiles) {
  if (tiles.length !== 14 || tiles.some((tile) => tile.suit === "z")) return false;
  const suit = tiles[0].suit;
  if (!tiles.every((tile) => tile.suit === suit)) return false;
  const counts = Array(10).fill(0);
  tiles.forEach((tile) => {
    counts[tile.number] += 1;
  });
  if (counts[1] < 3 || counts[9] < 3) return false;
  for (let number = 2; number <= 8; number += 1) {
    if (counts[number] < 1) return false;
  }
  return true;
}

function isValuedPair(index, context) {
  if ([31, 32, 33].includes(index)) return true;
  const windIndexes = { 東: 27, 南: 28, 西: 29, 北: 30 };
  return index === windIndexes[context.seat] || index === windIndexes[context.round];
}

function isTerminalOrHonorIndex(index) {
  return index >= 27 || index % 9 === 0 || index % 9 === 8;
}

function isHonorIndex(index) {
  return index >= 27;
}

function getMeldTiles(player) {
  return state.melds[player].flatMap((meld) => meld.tiles);
}

function countDora(tiles) {
  if (!state.doraIndicator) return 0;
  const doraIndex = getDoraTileType(state.doraIndicator).index;
  return tiles.filter((tile) => tile.tileIndex === doraIndex).length;
}

function countUraDora(tiles) {
  if (!state.uraDoraIndicator) return 0;
  const doraIndex = getDoraTileType(state.uraDoraIndicator).index;
  return tiles.filter((tile) => tile.tileIndex === doraIndex).length;
}

function countRedDora(tiles) {
  return tiles.filter((tile) => tile.tone === "flower").length;
}

function getDoraTileType(indicator) {
  const index = indicator.tileIndex ?? indicator.index;
  if (index < 27) {
    const suitStart = Math.floor(index / 9) * 9;
    return allTileTypes[suitStart + ((index - suitStart + 1) % 9)];
  }
  if (index >= 27 && index <= 30) return allTileTypes[27 + ((index - 27 + 1) % 4)];
  return allTileTypes[31 + ((index - 31 + 1) % 3)];
}

function getAgariPayments(han, fu, isDealer) {
  const base = getLimitedBase(han, fu);
  const honbaRon = state.honba * 300;
  const honbaTsumo = state.honba * 100;

  if (isDealer) {
    const baseRon = ceilHundred(base * 6);
    const baseTsumoAll = ceilHundred(base * 2);
    const ron = baseRon + honbaRon;
    const tsumoAll = baseTsumoAll + honbaTsumo;
    return {
      ron,
      tsumoAll,
      tsumoDealer: tsumoAll,
      tsumoChild: tsumoAll,
      base: {
        ron: baseRon,
        tsumoAll: baseTsumoAll,
        tsumoDealer: baseTsumoAll,
        tsumoChild: baseTsumoAll,
      },
    };
  }

  const baseRon = ceilHundred(base * 4);
  const baseTsumoDealer = ceilHundred(base * 2);
  const baseTsumoChild = ceilHundred(base);
  return {
    ron: baseRon + honbaRon,
    tsumoDealer: baseTsumoDealer + honbaTsumo,
    tsumoChild: baseTsumoChild + honbaTsumo,
    tsumoAll: 0,
    base: {
      ron: baseRon,
      tsumoDealer: baseTsumoDealer,
      tsumoChild: baseTsumoChild,
      tsumoAll: 0,
    },
  };
}

function getLimitedBase(han, fu) {
  const rawBase = fu * (2 ** (han + 2));
  if (han >= 13) return 8000;
  if (han >= 11) return 6000;
  if (han >= 8) return 4000;
  if (han >= 6) return 3000;
  if (han >= 5 || (han === 4 && fu >= 40) || (han === 3 && fu >= 70)) return 2000;
  return rawBase;
}

function ceilHundred(points) {
  return Math.ceil(points / 100) * 100;
}

function formatTsumoPoints(payments, isDealer) {
  if (isDealer) return `${payments.tsumoAll}点オール`;
  return `${payments.tsumoChild}/${payments.tsumoDealer}点`;
}

function isTanyao(tiles) {
  return tiles.every((tile) => tile.suit !== "z" && tile.number >= 2 && tile.number <= 8);
}

function countYakuhaiTriplets(counts, winner) {
  const dragonIndexes = [31, 32, 33];
  const windIndexes = { 東: 27, 南: 28, 西: 29, 北: 30 };
  const useful = new Set([...dragonIndexes, windIndexes.東, windIndexes[seatWind(winner)]]);
  return [...useful].filter((index) => counts[index] >= 3).length;
}
