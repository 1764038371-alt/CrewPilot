function declareRiichi() {
  if (state.current !== "bottom" || state.riichiPlayers.bottom) return;
  declareRiichiFor("bottom");
  log("リーチ宣言。次に切る牌が横向きの宣言牌になります。");
  render();
}

function declareRiichiFor(player) {
  state.riichiPlayers[player] = true;
  state.riichi = Boolean(state.riichiPlayers.bottom);
  state.ippatsuEligible[player] = true;
  state.riichiPending = player;
  state.scores[player] -= 1000;
  state.riichiSticks += 1;
  recordPaifuEvent("riichi", { player });
}

function canRon() {
  if (isCpuOnlyMode()) return false;
  if (state.current === "ron" && state.pendingRon?.winner === "bottom") return true;
  const target = getBottomRonTarget();
  return Boolean(target && isValidAgariForPlayer("bottom", "ロン", target.tile));
}

function getBottomRonTarget() {
  if (state.pendingRon?.winner === "bottom") return state.pendingRon;
  if (state.lastDiscard && state.lastDiscard.player !== "bottom") {
    return { winner: "bottom", tile: state.lastDiscard.tile, discarder: state.lastDiscard.player };
  }
  const latestDiscard = getLatestPaifuDiscard();
  if (!latestDiscard || latestDiscard.player === "bottom") return null;
  return {
    winner: "bottom",
    tile: tileFromCompact(latestDiscard.tile),
    discarder: latestDiscard.player,
  };
}

function getLatestPaifuDiscard() {
  const events = currentPaifuRound()?.events ?? [];
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (event.type === "decision") continue;
    if (event.type !== "discard") return null;
    return event;
  }
  return null;
}

function tileFromCompact(tile) {
  if (!tile) return null;
  const base = allTileTypes[tile.index];
  return base ? { ...base, tileIndex: tile.index, tone: tile.red ? "flower" : base.tone } : null;
}

function canTsumo() {
  if (isCpuOnlyMode()) return false;
  return state.current === "bottom" && !state.awaitingDraw && isValidAgariForPlayer("bottom", "ツモ");
}

function findRonWinner(discarder, tile) {
  const discardIndex = players.indexOf(discarder);
  for (let offset = 1; offset < players.length; offset += 1) {
    const player = players[(discardIndex + offset) % players.length];
    if (player === "bottom" && !isCpuOnlyMode()) continue;
    if (isValidAgariForPlayer(player, "ロン", tile)) return player;
  }
  return null;
}

function canRiichi() {
  if (isCpuOnlyMode()) return false;
  if (state.current !== "bottom" || state.awaitingDraw || state.riichiPlayers.bottom) return false;
  return findRiichiDiscardIndex("bottom") !== -1;
}

function canKan() {
  if (state.current !== "bottom") return false;
  return findKanTiles().length > 0;
}

function findKanTiles() {
  const counts = countTiles(state.hands.bottom);
  return allTileTypes.filter((tile) => counts[tile.index] === 4);
}

function getCallChoices(tile, fromPlayer) {
  if (state.riichi) return [];
  if (state.noCallMode) return [];
  if (fromPlayer === "bottom") return [];

  const counts = countTiles(state.hands.bottom);
  const choices = [];
  if (counts[tile.tileIndex] >= 2) choices.push({ type: "ポン", label: `ポン ${tile.mark}`, tile, fromPlayer });
  if (counts[tile.tileIndex] >= 3) choices.push({ type: "大明槓", label: `槓 ${tile.mark}`, tile, fromPlayer });

  if (fromPlayer === "left" && tile.suit !== "z") {
    const n = tile.number;
    const sequences = [
      [n - 2, n - 1],
      [n - 1, n + 1],
      [n + 1, n + 2],
    ];
    sequences.forEach((sequence) => {
      if (sequence.every((value) => value >= 1 && value <= 9 && counts[tileIndexFor(tile.suit, value)] > 0)) {
        choices.push({ type: "チー", label: `チー ${sequence.join("-")}`, tile, fromPlayer, sequence });
      }
    });
  }

  return choices;
}

function getCallChoicesForPlayer(player, tile, fromPlayer) {
  if (player === fromPlayer || state.riichiPlayers[player]) return [];
  const counts = countTiles(state.hands[player]);
  const choices = [];
  if (counts[tile.tileIndex] >= 2) choices.push({ player, type: "ポン", label: `ポン ${tile.mark}`, tile, fromPlayer });

  if (player === nextPlayer(fromPlayer) && tile.suit !== "z") {
    const n = tile.number;
    const sequences = [
      [n - 2, n - 1],
      [n - 1, n + 1],
      [n + 1, n + 2],
    ];
    sequences.forEach((sequence) => {
      if (sequence.every((value) => value >= 1 && value <= 9 && counts[tileIndexFor(tile.suit, value)] > 0)) {
        choices.push({ player, type: "チー", label: `チー ${sequence.join("-")}`, tile, fromPlayer, sequence });
      }
    });
  }
  return choices;
}

function findCpuCall(fromPlayer, tile) {
  const callers = players
    .filter((player) => player !== fromPlayer)
    .filter((player) => isCpuOnlyMode() || player !== "bottom")
    .filter((player) => !state.riichiPlayers[player]);
  const choices = callers.flatMap((player) => getCallChoicesForPlayer(player, tile, fromPlayer));
  const assessments = choices.map(assessCpuCall).filter((assessment) => assessment.plan);
  if (assessments.length === 0) return null;
  assessments.sort((a, b) => b.score - a.score);
  const best = assessments[0];
  const shouldCall = Math.random() < best.rate;
  recordCpuCallDecision(best, shouldCall);
  return shouldCall ? { ...best.choice, plan: best.plan } : null;
}

function assessCpuCall(choice) {
  const player = choice.player;
  const before = getBestShantenForPlayer(player);
  const afterHand = simulateHandAfterCall(player, choice);
  const after = getBestShantenForPlayer(player, afterHand);
  const postCall = getPostCallTenpaiInfo(choice, afterHand);
  const yakuPlan = getOpenCallYakuPlan(choice, afterHand) || getPostCallTenpaiPlan(postCall);
  const formalPlan = getFormalTenpaiPlan(postCall);
  const plan = yakuPlan || formalPlan;
  const attackBias = { calm: 0.35, normal: 0.55, hard: 0.78 }[state.rules.cpuAttack] ?? 0.55;
  if (!plan) return { choice, before, after, plan: null, rate: 0, score: -999 };
  const shantenGain = before - after;
  if (!postCall.yakuTenpai && !postCall.formalTenpai && (shantenGain < 0 || after > 2)) {
    return { choice, before, after, plan, rate: 0, score: -999 };
  }
  const features = getCpuCallFeatures(plan, shantenGain, choice, postCall);
  const learnedBonus = Math.max(-0.25, Math.min(0.25, scoreCpuFeatures(features) / 900));
  const mustOpenBonus = getMustOpenBonus(choice, plan, before, after) + getTenpaiCallBonus(choice, postCall);
  const baseRate = shantenGain > 0
    ? attackBias * plan.rate + mustOpenBonus
    : shantenGain === 0
      ? attackBias * plan.rate * getSameShantenCallMultiplier(postCall) + mustOpenBonus
      : 0;
  const rate = baseRate + learnedBonus;
  return {
    choice,
    before,
    after,
    plan,
    postCall,
    features,
    rate: Math.max(0, Math.min(0.98, rate)),
    score: callPriority(choice) * 100 + shantenGain * 40 + plan.rate * 10 + mustOpenBonus * 100,
  };
}

function getPostCallTenpaiInfo(choice, afterHand) {
  const player = choice.player;
  const tempMeld = makeTempMeld(choice);
  state.melds[player].push(tempMeld);
  try {
    const candidates = afterHand.map((_, index) => afterHand.filter((__, tileIndex) => tileIndex !== index));
    const yakuWaits = candidates.flatMap((hand) => getYakuWaitsForPlayer(player, hand));
    const formalWaits = candidates.flatMap((hand) => getWaitsForPlayer(player, hand));
    return {
      yakuTenpai: yakuWaits.length > 0,
      formalTenpai: formalWaits.length > 0,
      yakuWaitCount: new Set(yakuWaits.map((tile) => tile.index)).size,
      formalWaitCount: new Set(formalWaits.map((tile) => tile.index)).size,
    };
  } finally {
    state.melds[player].pop();
  }
}

function makeTempMeld(choice) {
  const indexes = getCallIndexes(choice);
  return {
    type: choice.type,
    fromPlayer: choice.fromPlayer,
    claimedIndex: 0,
    tiles: indexes.map((index) => ({ ...allTileTypes[index], tileIndex: index })),
  };
}

function getPostCallTenpaiPlan(postCall) {
  if (!postCall.yakuTenpai) return null;
  return { name: "役あり聴牌", rate: 1.42 };
}

function getFormalTenpaiPlan(postCall) {
  if (!postCall.formalTenpai || state.wall.length > 30) return null;
  return { name: "形式聴牌", rate: 0.9 };
}

function getTenpaiCallBonus(choice, postCall) {
  const phase = getRoundPhase();
  if (postCall.yakuTenpai) {
    if (phase === "late") return choice.type === "ポン" ? 0.72 : 0.66;
    if (phase === "middle") return choice.type === "ポン" ? 0.54 : 0.46;
    return 0.16;
  }
  if (postCall.formalTenpai && phase === "late") return 0.42;
  return 0;
}

function getSameShantenCallMultiplier(postCall) {
  if (postCall.yakuTenpai) return 0.9;
  if (postCall.formalTenpai && state.wall.length <= 30) return 0.72;
  return 0.55;
}

function getRoundPhase() {
  if (state.wall.length <= 30) return "late";
  if (state.wall.length <= 56) return "middle";
  return "early";
}

function getMustOpenBonus(choice, plan, beforeShanten, afterShanten) {
  if (plan.name !== "役牌" || choice.type !== "ポン") return 0;
  const player = choice.player;
  const openHand = state.melds[player].length > 0;
  const noOtherOpenPlan = !state.openYakuPlans[player];
  const closeToAgari = afterShanten <= 2;
  const noRiichiRoute = openHand || beforeShanten <= 2;
  if (closeToAgari && (noOtherOpenPlan || noRiichiRoute)) return 0.38;
  return 0.18;
}

function getCpuCallFeatures(plan, shantenGain, choice, postCall = {}) {
  return {
    callTaken: 1,
    callShantenGain: Math.max(0, shantenGain),
    callYakuhai: plan.name === "役牌" ? 1 : 0,
    callHonitsu: plan.name === "混一色" ? 1 : 0,
    callIttsu: plan.name === "一気通貫" ? 1 : 0,
    callSanshoku: plan.name === "三色同順" ? 1 : 0,
    callTanyao: plan.name === "断么九" ? 1 : 0,
    callYakuTenpai: plan.name === "役あり聴牌" ? 1 : 0,
    callFormalTenpai: plan.name === "形式聴牌" ? 1 : 0,
    callAsDealer: choice.player === players[state.dealerIndex] ? 1 : 0,
    callAgainstDealer: choice.fromPlayer === players[state.dealerIndex] ? 1 : 0,
    callNeedSpeed: shouldPreferSpeed(choice.player) ? 1 : 0,
    callNeedPoints: shouldPreferPoints(choice.player) ? 1 : 0,
    callMiddleOrLater: state.wall.length <= 56 ? 1 : 0,
    callLate: state.wall.length <= 30 ? 1 : 0,
    callYakuWaitCount: postCall.yakuWaitCount ?? 0,
    callFormalWaitCount: postCall.formalWaitCount ?? 0,
    ...getScoreSituationFeatures(choice.player, "call"),
  };
}

function callPriority(choice) {
  const plan = getOpenCallYakuPlan(choice, simulateHandAfterCall(choice.player, choice));
  if (plan?.name === "役牌") return 6;
  if (plan?.name === "混一色") return 5;
  if (plan?.name === "一気通貫") return 4;
  if (plan?.name === "三色同順") return 3;
  if (plan?.name === "断么九") return 2;
  return 1;
}

function simulateHandAfterCall(player, choice) {
  const hand = [...state.hands[player]];
  const indexes = choice.type === "チー"
    ? choice.sequence.map((number) => tileIndexFor(choice.tile.suit, number))
    : [choice.tile.tileIndex, choice.tile.tileIndex];
  indexes.forEach((tileIndex) => {
    const index = hand.findIndex((tile) => tile.tileIndex === tileIndex);
    if (index !== -1) hand.splice(index, 1);
  });
  return hand;
}

function getOpenCallYakuPlan(choice, afterHand) {
  const player = choice.player;
  const callIndexes = getCallIndexes(choice);
  const allIndexes = [
    ...afterHand.map((tile) => tile.tileIndex),
    ...getMeldTiles(player).map((tile) => tile.tileIndex),
    ...callIndexes,
  ];
  const context = { seat: seatWind(player), round: roundWind() };
  const honitsuSuit = getHonitsuRouteSuit(allIndexes);
  const ittsuSuit = getIttsuRouteSuit(allIndexes);
  const sanshokuStart = getSanshokuRouteStart(allIndexes);

  if (choice.type === "ポン" && isValuedPair(choice.tile.tileIndex, context)) {
    return { name: "役牌", rate: 1.25, tileIndex: choice.tile.tileIndex };
  }
  if (hasYakuhaiTripletRoute(allIndexes, context)) return { name: "役牌", rate: 1.1 };
  if (hasYakuhaiPairRoute(allIndexes, context)) return { name: "役牌", rate: 0.92 };
  if (honitsuSuit !== null) return { name: "混一色", rate: 1.05, targetSuit: honitsuSuit };
  if (ittsuSuit !== null) return { name: "一気通貫", rate: 0.95, targetSuit: ittsuSuit };
  if (sanshokuStart !== null) return { name: "三色同順", rate: 0.85, startNumber: sanshokuStart };
  if (hasTanyaoRoute(allIndexes)) return { name: "断么九", rate: 0.75 };
  return null;
}

function hasYakuhaiPairRoute(indexes, context) {
  const counts = Array(34).fill(0);
  indexes.forEach((index) => {
    counts[index] += 1;
  });
  return [27, 28, 29, 30, 31, 32, 33].some((index) => counts[index] >= 2 && isValuedPair(index, context));
}

function hasYakuhaiTripletRoute(indexes, context) {
  const counts = Array(34).fill(0);
  indexes.forEach((index) => {
    counts[index] += 1;
  });
  return [27, 28, 29, 30, 31, 32, 33].some((index) => counts[index] >= 3 && isValuedPair(index, context));
}

function getCallIndexes(choice) {
  if (choice.type === "チー") {
    return [choice.tile.tileIndex, ...choice.sequence.map((number) => tileIndexFor(choice.tile.suit, number))];
  }
  return [choice.tile.tileIndex, choice.tile.tileIndex, choice.tile.tileIndex];
}

function hasTanyaoRoute(indexes) {
  return indexes.length > 0 && indexes.every((index) => index < 27 && index % 9 !== 0 && index % 9 !== 8);
}

function hasHonitsuRoute(indexes) {
  return getHonitsuRouteSuit(indexes) !== null;
}

function getHonitsuRouteSuit(indexes) {
  const suitIndexes = indexes.filter((index) => index < 27);
  if (suitIndexes.length < 7) return null;
  const suitsFound = new Set(suitIndexes.map((index) => Math.floor(index / 9)));
  return suitsFound.size === 1 ? [...suitsFound][0] : null;
}

function hasIttsuRoute(indexes) {
  return getIttsuRouteSuit(indexes) !== null;
}

function getIttsuRouteSuit(indexes) {
  for (let suit = 0; suit < 3; suit += 1) {
    const start = suit * 9;
    const blocks = [
      [start, start + 1, start + 2],
      [start + 3, start + 4, start + 5],
      [start + 6, start + 7, start + 8],
    ];
    if (blocks.every((block) => block.filter((index) => indexes.includes(index)).length >= 2)) return suit;
  }
  return null;
}

function hasSanshokuRoute(indexes) {
  return getSanshokuRouteStart(indexes) !== null;
}

function getSanshokuRouteStart(indexes) {
  for (let number = 1; number <= 7; number += 1) {
    const starts = [0, 9, 18].map((start) => start + number - 1);
    if (starts.every((start) => [start, start + 1, start + 2].filter((index) => indexes.includes(index)).length >= 2)) return number;
  }
  return null;
}

function claimCpuCall(choice) {
  clearIppatsu();
  const river = state.rivers[choice.fromPlayer];
  const claimed = river.pop();
  if (!claimed) return;

  const usedTiles = [];
  if (choice.type === "ポン") {
    usedTiles.push(...takeTilesFromHand(choice.player, choice.tile.tileIndex, 2));
  } else if (choice.type === "チー") {
    choice.sequence.forEach((number) => {
      usedTiles.push(...takeTilesFromHand(choice.player, tileIndexFor(choice.tile.suit, number), 1));
    });
  }

  const meldTiles = buildMeldTiles(choice, usedTiles, claimed.tile);
  state.melds[choice.player].push({
    type: choice.type,
    fromPlayer: choice.fromPlayer,
    tiles: meldTiles.tiles,
    claimedIndex: meldTiles.claimedIndex,
  });
  setOpenYakuPlan(choice.player, choice.plan);
  sortHand(choice.player);
  state.current = choice.player;
  state.awaitingDraw = false;
  state.callChoices = [];
  state.lastDiscard = null;
  recordPaifuEvent("call", { player: choice.player, fromPlayer: choice.fromPlayer, tile: claimed.tile });
  log(`${playerName(choice.player)} ${choice.type} ${claimed.tile.mark}`);
  render();
  scheduleCpu(() => {
    if (state.paused) {
      state.resumeAction = () => {
        if (state.roundEnded || state.current !== choice.player) return;
        const caller = choice.player;
        discardCpuTile(caller, chooseCpuDiscard(state.hands[caller], caller));
        if (state.current === "call" || state.current === "ron" || state.current === "ended" || state.current !== caller) return;
        if (isCpuOnlyMode()) {
          scheduleCpu(() => continueCpuOnlyCycle(players.indexOf(nextPlayer(caller))), 240);
          return;
        }
        const cpuPlayers = ["right", "top", "left"];
        scheduleCpu(() => continueCpuCycle(cpuPlayers.indexOf(caller) + 1), 240);
      };
      return;
    }
    if (state.roundEnded || state.current !== choice.player) return;
    const caller = choice.player;
    discardCpuTile(caller, chooseCpuDiscard(state.hands[caller], caller));
    if (state.current === "call" || state.current === "ron" || state.current === "ended" || state.current !== caller) return;
    if (isCpuOnlyMode()) {
      scheduleCpu(() => continueCpuOnlyCycle(players.indexOf(nextPlayer(caller))), 240);
      return;
    }
    const cpuPlayers = ["right", "top", "left"];
    scheduleCpu(() => continueCpuCycle(cpuPlayers.indexOf(caller) + 1), 240);
  }, 240);
}

function setOpenYakuPlan(player, plan) {
  if (!plan) return;
  const current = state.openYakuPlans[player];
  if (!current || openYakuPlanPriority(plan) >= openYakuPlanPriority(current)) {
    state.openYakuPlans[player] = plan;
  }
}

function openYakuPlanPriority(plan) {
  return {
    "役あり聴牌": 6,
    "役牌": 5,
    "混一色": 4,
    "一気通貫": 3,
    "三色同順": 3,
    "断么九": 2,
    "形式聴牌": 1,
  }[plan?.name] ?? 0;
}

function tileIndexFor(suit, number) {
  const suitOffset = { m: 0, p: 9, s: 18 }[suit];
  return suitOffset + number - 1;
}

function renderCallPanel() {
  const panel = $("callPanel");
  panel.innerHTML = "";
  if (!state.ronPending && (state.current !== "call" || state.callChoices.length === 0)) {
    panel.hidden = true;
    return;
  }

  panel.hidden = false;
  state.callChoices.forEach((choice) => {
    const button = document.createElement("button");
    button.textContent = choice.label;
    button.addEventListener("click", () => {
      claimCall(choice);
    });
    panel.appendChild(button);
  });

  const skipButton = document.createElement("button");
  skipButton.textContent = "スキップ";
  skipButton.addEventListener("click", skipCall);
  panel.appendChild(skipButton);
}

function skipCall() {
  state.callChoices = [];
  state.ronPending = false;
  state.pendingRon = null;
  log(state.current === "ron" ? "ロンをスキップしました。" : "副露をスキップしました。");
  continueCpuCycle(state.pendingCpuIndex);
}

function canShowAutoWinButton() {
  return getVisibleWaits().length > 0 || canRon() || canTsumo();
}

function toggleAutoWin() {
  state.autoWin = !state.autoWin;
  log(`自動和了を${state.autoWin ? "オン" : "オフ"}にしました。`);
  if (state.autoWin && canRon()) {
    declareRon();
    return;
  }
  if (state.autoWin && canTsumo()) {
    declareTsumo();
    return;
  }
  render();
}

function toggleNoCallMode() {
  state.noCallMode = !state.noCallMode;
  if (state.noCallMode && state.current === "call") {
    state.callChoices = [];
    log("鳴きなしをオンにしました。副露候補を表示しません。");
    continueCpuCycle(state.pendingCpuIndex);
    return;
  }
  log(`鳴きなしを${state.noCallMode ? "オン" : "オフ"}にしました。`);
  render();
}

function claimCall(choice) {
  clearIppatsu();
  const river = state.rivers[choice.fromPlayer];
  const claimed = river.pop();
  const usedTiles = [];

  if (choice.type === "ポン") {
    usedTiles.push(...takeTilesFromHand("bottom", choice.tile.tileIndex, 2));
  } else if (choice.type === "大明槓") {
    usedTiles.push(...takeTilesFromHand("bottom", choice.tile.tileIndex, 3));
  } else if (choice.type === "チー") {
    choice.sequence.forEach((number) => {
      usedTiles.push(...takeTilesFromHand("bottom", tileIndexFor(choice.tile.suit, number), 1));
    });
  }

  const claimedTile = claimed.tile;
  const meldTiles = buildMeldTiles(choice, usedTiles, claimedTile);
  state.melds.bottom.push({
    type: choice.type,
    fromPlayer: choice.fromPlayer,
    tiles: meldTiles.tiles,
    claimedIndex: meldTiles.claimedIndex,
  });
  sortHand("bottom");
  state.current = "bottom";
  state.awaitingDraw = false;
  state.callChoices = [];
  state.lastDiscard = null;
  recordPaifuEvent("call", { player: "bottom", fromPlayer: choice.fromPlayer, tile: claimedTile });
  log(`${choice.type}しました。手牌から1枚切ってください。`);
  render();
}

function clearIppatsu() {
  players.forEach((player) => {
    state.ippatsuEligible[player] = false;
  });
}

function buildMeldTiles(choice, usedTiles, claimedTile) {
  if (choice.type === "チー") {
    const tiles = [claimedTile, ...usedTiles.sort((a, b) => a.order - b.order)];
    return {
      tiles,
      claimedIndex: 0,
    };
  }

  const claimedIndexBySource = {
    left: 0,
    top: 1,
    right: 2,
  };
  const sourceSeat = relativeVisualSeat(choice.fromPlayer, choice.player ?? "bottom");
  const claimedIndex = claimedIndexBySourceSeat(claimedIndexBySource, sourceSeat, usedTiles.length);
  const tiles = [...usedTiles];
  tiles.splice(claimedIndex, 0, claimedTile);
  return { tiles, claimedIndex };
}

function claimedIndexBySourceSeat(indexes, sourceSeat, fallback) {
  return indexes[sourceSeat] ?? fallback;
}

function takeTilesFromHand(player, tileIndex, amount) {
  const taken = [];
  for (let count = 0; count < amount; count += 1) {
    const index = state.hands[player].findIndex((tile) => tile.tileIndex === tileIndex);
    if (index === -1) break;
    taken.push(...state.hands[player].splice(index, 1));
  }
  return taken;
}
