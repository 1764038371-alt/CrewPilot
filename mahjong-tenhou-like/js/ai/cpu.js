function chooseCpuDiscard(hand, player) {
  const candidates = hand.map((tile, index) => ({ tile, index }));
  const scored = candidates.map(({ tile, index }) => {
    const trial = hand.filter((__, tileIndex) => tileIndex !== index);
    const features = extractCpuFeatures(trial, tile, player);
    const shanten = getBestShantenForPlayer(player, trial);
    const yakuWaits = getYakuWaitsForPlayer(player, trial);
    const decoratedFeatures = addDiscardContextFeatures(features, player, trial, yakuWaits);
    const defense = assessDiscardDefense(player, tile, trial, shanten, yakuWaits);
    const fullFeatures = { ...decoratedFeatures, ...defense.features };
    const planScore = scoreOpenYakuPlanDiscard(player, trial, tile);
    const structureScore = scoreMentsuIntegrity(hand, trial, tile, player);
    return {
      index,
      features: fullFeatures,
      shanten,
      yakuWaits,
      defense,
      score: scoreCpuFeatures(fullFeatures) + planScore + structureScore + defense.score,
    };
  });
  const yakuTenpaiCandidates = scored
    .filter((item) => item.yakuWaits.length > 0)
    .sort((a, b) => b.yakuWaits.length - a.yakuWaits.length || b.score - a.score);
  if (yakuTenpaiCandidates.length > 0) {
    const picked = yakuTenpaiCandidates[0];
    const alternatives = scored
      .filter((item) => item.index !== picked.index)
      .sort((a, b) => b.score - a.score)
      .slice(0, 5)
      .map((item) => item.features);
    recordCpuDecision(player, { ...picked.features, yakuTenpaiKept: 1 }, alternatives, discardDecisionMeta(hand, picked, scored, "役あり聴牌を維持"));
    return picked.index;
  }
  const bestShanten = Math.min(...scored.map((item) => item.shanten));
  const mustFold = shouldCpuPreferDefense(player, bestShanten);
  const viable = scored
    .filter((item) => mustFold || item.shanten === bestShanten)
    .sort((a, b) => b.score - a.score)
    .slice(0, 5);
  const explorationRate = getCpuExplorationRate(player, bestShanten);
  const pool = viable.length >= 3 ? viable : scored.sort((a, b) => b.score - a.score).slice(0, 5);
  const picked = Math.random() < explorationRate ? pool[Math.floor(Math.random() * pool.length)] : pool[0];
  recordCpuDecision(
    player,
    picked.features,
    pool.filter((item) => item.index !== picked.index).map((item) => item.features),
    discardDecisionMeta(hand, picked, pool)
  );
  return picked.index;
}

function discardDecisionMeta(hand, picked, candidates, forcedReason = "") {
  const tile = hand[picked.index];
  return {
    action: "打牌",
    tile,
    score: picked.score,
    shanten: picked.shanten,
    waits: picked.yakuWaits?.length ?? 0,
    reason: forcedReason || describeDiscardDecision(picked),
    alternatives: candidates
      .filter((item) => item.index !== picked.index)
      .sort((a, b) => b.score - a.score)
      .slice(0, 5)
      .map((item) => ({
        tile: hand[item.index],
        score: item.score,
        shanten: item.shanten,
        reason: describeDiscardDecision(item),
      })),
  };
}

function describeDiscardDecision(item) {
  if (item.yakuWaits?.length > 0) return "役あり聴牌";
  if (item.features?.openPlanKept) return "副露後の手役方針を維持";
  if (item.features?.defenseFold) return "守備優先";
  if (item.features?.defenseSafe) return "安全度高め";
  if (item.features?.defensePush) return "聴牌/好形で押し";
  if (item.shanten <= 0) return "聴牌維持";
  return `${item.shanten}向聴を維持`;
}

function assessDiscardDefense(player, discardedTile, handAfterDiscard, shanten, yakuWaits) {
  const threats = getThreatPlayers(player);
  if (threats.length === 0 || !discardedTile) {
    return { danger: 0, score: 0, features: {} };
  }
  const danger = Math.max(...threats.map((threat) => getTileDangerAgainstThreat(discardedTile, threat, handAfterDiscard)));
  const hasYakuTenpai = yakuWaits.length > 0;
  const push = hasYakuTenpai || shanten <= 0;
  const fold = shouldCpuPreferDefense(player, shanten) && !push;
  const defenseScale = fold ? 7.5 : push ? 1.4 : 3.4;
  const safeBonus = danger <= 8 ? 260 : danger <= 18 ? 110 : 0;
  const score = safeBonus - danger * defenseScale;
  return {
    danger,
    score,
    features: {
      defenseSafe: danger <= 8 ? 1 : 0,
      defenseDanger: danger / 100,
      defenseFold: fold ? 1 : 0,
      defensePush: push ? 1 : 0,
      defenseAgainstRiichi: threats.some((threat) => state.riichiPlayers[threat]) ? 1 : 0,
      defenseDoraDanger: isDoraDangerTile(discardedTile) ? 1 : 0,
    },
  };
}

function shouldCpuPreferDefense(player, shanten) {
  const threats = getThreatPlayers(player);
  if (threats.length === 0) return false;
  if (shanten <= 0) return false;
  if (state.wall.length <= 24) return true;
  if (isTopPlayer(player) && state.wall.length <= 42) return true;
  return shanten >= 2;
}

function getThreatPlayers(player) {
  return players.filter((other) => (
    other !== player &&
    (state.riichiPlayers[other] || isDangerousOpenHand(other))
  ));
}

function isDangerousOpenHand(player) {
  const meldCount = state.melds[player]?.length ?? 0;
  if (meldCount >= 3) return true;
  if (meldCount >= 2 && state.wall.length <= 36) return true;
  return false;
}

function getTileDangerAgainstThreat(tile, threat, handAfterDiscard) {
  if (isGenbutsu(tile, threat)) return 0;
  const visibleCount = countVisibleTile(tile.tileIndex, handAfterDiscard);
  let danger = 34;

  if (tile.suit === "z") {
    danger = visibleCount >= 3 ? 6 : visibleCount >= 2 ? 16 : 30;
  } else {
    if (isSujiSafe(tile, threat)) danger -= 18;
    if (tile.number === 1 || tile.number === 9) danger -= 8;
    if (tile.number === 2 || tile.number === 8) danger += 2;
    if (tile.number >= 4 && tile.number <= 6) danger += 10;
    if (visibleCount >= 3) danger -= 18;
    else if (visibleCount === 2) danger -= 8;
  }

  if (isDoraDangerTile(tile)) danger += 24;
  if (isRiichiThreatFresh(threat)) danger += 8;
  if (state.riichiPlayers[threat]) danger += 12;
  return Math.max(0, Math.min(100, danger));
}

function isGenbutsu(tile, threat) {
  return state.rivers[threat]?.some((entry) => entry.tile.tileIndex === tile.tileIndex);
}

function isSujiSafe(tile, threat) {
  if (tile.suit === "z") return false;
  const discardedNumbers = new Set(
    state.rivers[threat]
      ?.map((entry) => entry.tile)
      .filter((riverTile) => riverTile.suit === tile.suit)
      .map((riverTile) => riverTile.number) ?? []
  );
  const safeByNumber = {
    1: [4],
    2: [5],
    3: [6],
    4: [1, 7],
    5: [2, 8],
    6: [3, 9],
    7: [4],
    8: [5],
    9: [6],
  };
  return (safeByNumber[tile.number] ?? []).some((number) => discardedNumbers.has(number));
}

function countVisibleTile(tileIndex, handAfterDiscard) {
  let count = handAfterDiscard.filter((tile) => tile.tileIndex === tileIndex).length;
  players.forEach((player) => {
    count += state.rivers[player]?.filter((entry) => entry.tile.tileIndex === tileIndex).length ?? 0;
    count += getMeldTiles(player).filter((tile) => tile.tileIndex === tileIndex).length;
  });
  return count;
}

function isDoraDangerTile(tile) {
  if (!tile || !state.doraIndicator) return false;
  const dora = getDoraTileType(state.doraIndicator);
  if (tile.tileIndex === dora.index) return true;
  if (tile.suit === "z" || dora.suit === "z" || tile.suit !== dora.suit) return false;
  return Math.abs(tile.number - dora.number) <= 1;
}

function isRiichiThreatFresh(threat) {
  const river = state.rivers[threat] ?? [];
  const riichiIndex = river.findIndex((entry) => entry.sideways);
  return riichiIndex !== -1 && river.length - riichiIndex <= 3;
}

function addDiscardContextFeatures(features, player, handAfterDiscard, yakuWaits) {
  const plan = state.openYakuPlans[player];
  if (!plan) {
    return {
      ...features,
      yakuTenpaiKept: yakuWaits.length > 0 ? 1 : 0,
    };
  }
  const planAlive = isOpenYakuPlanAlive(player, handAfterDiscard, plan);
  return {
    ...features,
    yakuTenpaiKept: yakuWaits.length > 0 ? 1 : 0,
    openPlanKept: planAlive ? 1 : 0,
    openPlanBroken: planAlive ? 0 : 1,
    openPlanTenpai: yakuWaits.length > 0 ? 1 : 0,
  };
}

function getCpuExplorationRate(player, bestShanten) {
  if (state.openYakuPlans[player] || bestShanten <= 1) return 0.06;
  if (!state.rules.cpuLearning) return 0.12;
  const learnedGames = state.ai.games ?? 0;
  const decay = Math.max(0.12, 1 - learnedGames / 50000);
  const base = state.rules.learningMode === "fast"
    ? 0.42
    : state.rules.learningMode === "accelerated"
      ? 0.34
      : 0.26;
  return Math.max(0.08, base * decay);
}

function scoreMentsuIntegrity(beforeHand, afterHand, discardedTile, player) {
  const before = countTiles(beforeHand);
  const after = countTiles(afterHand);
  const index = discardedTile.tileIndex;
  let score = 0;

  if (before[index] === 3) score -= 520;
  if (before[index] === 2) {
    const context = { seat: seatWind(player), round: roundWind() };
    score -= isValuedPair(index, context) ? 180 : 80;
  }

  const sequenceLoss = countCompleteSequences(before) - countCompleteSequences(after);
  if (sequenceLoss > 0) score -= sequenceLoss * 280;

  const blockLoss = countUsefulBlocks(before) - countUsefulBlocks(after);
  if (blockLoss > 0) score -= blockLoss * 55;

  if (isTileFloating(before, index)) score += 120;
  return score;
}

function countCompleteSequences(counts) {
  let sequences = 0;
  for (let suit = 0; suit < 3; suit += 1) {
    const start = suit * 9;
    for (let offset = 0; offset <= 6; offset += 1) {
      sequences += Math.min(counts[start + offset], counts[start + offset + 1], counts[start + offset + 2]);
    }
  }
  return sequences;
}

function isTileFloating(counts, index) {
  if (counts[index] >= 2) return false;
  if (index >= 27) return true;
  const suitStart = Math.floor(index / 9) * 9;
  const pos = index - suitStart;
  return [-2, -1, 1, 2].every((offset) => {
    const other = pos + offset;
    return other < 0 || other > 8 || counts[suitStart + other] === 0;
  });
}

function scoreOpenYakuPlanDiscard(player, handAfterDiscard, discardedTile) {
  const plan = state.openYakuPlans[player];
  if (!plan || !discardedTile) return 0;
  const index = discardedTile.tileIndex;
  const alivePenalty = isOpenYakuPlanAlive(player, handAfterDiscard, plan) ? 0 : -900;
  if (plan.name === "混一色") return scoreHonitsuPlanDiscard(player, handAfterDiscard, discardedTile, plan);
  if (plan.name === "一気通貫") return scoreIttsuPlanDiscard(discardedTile, plan) + alivePenalty;
  if (plan.name === "三色同順") return scoreSanshokuPlanDiscard(discardedTile, plan) + alivePenalty;
  if (plan.name === "断么九") return (isTerminalOrHonorIndex(index) ? 180 : -180) + alivePenalty;
  if (plan.name === "役牌") return scoreYakuhaiPlanDiscard(player, handAfterDiscard, discardedTile, plan) + alivePenalty;
  if (plan.name === "役あり聴牌") return getYakuWaitsForPlayer(player, handAfterDiscard).length > 0 ? 360 : -900;
  if (plan.name === "形式聴牌") return getWaitsForPlayer(player, handAfterDiscard).length > 0 ? 120 : -420;
  return alivePenalty;
}

function scoreHonitsuPlanDiscard(player, handAfterDiscard, discardedTile, plan) {
  const targetSuit = plan.targetSuit ?? detectMainSuit([...handAfterDiscard, ...getMeldTiles(player)]);
  if (targetSuit === null) return 0;
  const suit = tileSuitNumber(discardedTile.tileIndex);
  const alivePenalty = isOpenYakuPlanAlive(player, handAfterDiscard, { ...plan, targetSuit }) ? 0 : -900;
  if (suit === "z") return -35;
  if (suit === targetSuit) return -260 + alivePenalty;
  return 300 + alivePenalty;
}

function isOpenYakuPlanAlive(player, hand, plan) {
  if (!plan) return true;
  const indexes = [
    ...hand.map((tile) => tile.tileIndex),
    ...getMeldTiles(player).map((tile) => tile.tileIndex),
  ];
  const counts = Array(34).fill(0);
  indexes.forEach((index) => {
    counts[index] += 1;
  });
  const context = { seat: seatWind(player), round: roundWind() };

  if (plan.name === "役牌") {
    if (plan.tileIndex !== undefined) return counts[plan.tileIndex] >= 3 || counts[plan.tileIndex] >= 2;
    return [27, 28, 29, 30, 31, 32, 33].some((index) => counts[index] >= 2 && isValuedPair(index, context));
  }
  if (plan.name === "混一色") {
    const targetSuit = plan.targetSuit ?? detectMainSuit(indexes.map((index) => allTileTypes[index]));
    return targetSuit !== null && indexes.every((index) => index >= 27 || Math.floor(index / 9) === targetSuit);
  }
  if (plan.name === "一気通貫") {
    return getIttsuRouteSuit(indexes) === (plan.targetSuit ?? getIttsuRouteSuit(indexes));
  }
  if (plan.name === "三色同順") {
    return getSanshokuRouteStart(indexes) === (plan.startNumber ?? getSanshokuRouteStart(indexes));
  }
  if (plan.name === "断么九") {
    return indexes.length > 0 && indexes.every((index) => index < 27 && index % 9 !== 0 && index % 9 !== 8);
  }
  if (plan.name === "役あり聴牌") return getYakuWaitsForPlayer(player, hand).length > 0;
  if (plan.name === "形式聴牌") return getWaitsForPlayer(player, hand).length > 0;
  return true;
}

function scoreIttsuPlanDiscard(discardedTile, plan) {
  if (discardedTile.suit === "z") return 55;
  const targetSuit = plan.targetSuit ?? Math.floor(discardedTile.tileIndex / 9);
  if (Math.floor(discardedTile.tileIndex / 9) !== targetSuit) return 85;
  return -180;
}

function scoreSanshokuPlanDiscard(discardedTile, plan) {
  if (discardedTile.suit === "z") return 45;
  const start = plan.startNumber;
  if (!start) return 0;
  return discardedTile.number >= start && discardedTile.number <= start + 2 ? -170 : 70;
}

function scoreYakuhaiPlanDiscard(player, handAfterDiscard, discardedTile, plan) {
  const context = { seat: seatWind(player), round: roundWind() };
  if (plan.tileIndex !== undefined && discardedTile.tileIndex === plan.tileIndex) return -320;
  if (isValuedPair(discardedTile.tileIndex, context)) {
    const countAfter = countTiles(handAfterDiscard)[discardedTile.tileIndex];
    return countAfter >= 1 ? -180 : 40;
  }
  return 0;
}

function detectMainSuit(tiles) {
  const counts = [0, 0, 0];
  tiles.forEach((tile) => {
    const index = tile.tileIndex ?? tile.index;
    if (index < 27) counts[Math.floor(index / 9)] += 1;
  });
  const max = Math.max(...counts);
  return max === 0 ? null : counts.indexOf(max);
}

function tileSuitNumber(index) {
  return index >= 27 ? "z" : Math.floor(index / 9);
}

function isTerminalOrHonorIndex(index) {
  return index >= 27 || index % 9 === 0 || index % 9 === 8;
}

function evaluateCpuKeepScore(hand) {
  return scoreCpuFeatures(extractCpuFeatures(hand, null, "bottom"));
}

function extractCpuFeatures(hand, discardedTile, player = "bottom") {
  const waits = getWaitsForPlayer(player, hand);
  const counts = countTiles(hand);
  let tenpaiDraws = 0;
  allTileTypes.forEach((tile) => {
    if (counts[tile.index] >= 4) return;
    if (getWaitsForPlayer(player, [...hand, tile]).length > 0) tenpaiDraws += 1;
  });
  return {
    waits: waits.length,
    tenpaiDraws,
    pairs: countPairs(counts),
    blocks: countUsefulBlocks(counts),
    isolated: countIsolatedTiles(hand),
    standardShanten: getStandardShantenForPlayer(player, hand),
    chiitoiShanten: getChiitoiShantenForPlayer(player, hand),
    terminalHonorDiscard: discardedTile && discardedTile.suit !== "z" && (discardedTile.number === 1 || discardedTile.number === 9) ? 1 : 0,
    honorDiscard: discardedTile?.suit === "z" ? 1 : 0,
  };
}

function scoreCpuFeatures(features) {
  const weights = state.ai.weights ?? defaultAiWeights();
  let score = features.waits > 0 ? 10000 : 0;
  Object.entries(features).forEach(([key, value]) => {
    score += (weights[key] ?? 0) * value;
  });
  return score;
}

function recordCpuDecision(player, features, alternatives = [], meta = {}) {
  if (!state.rules.cpuLearning) return;
  if (player === "bottom" && !isCpuOnlyMode()) return;
  const decision = { player, features, alternatives };
  state.ai.decisions.push(decision);
  state.ai.roundDecisions.push(decision);
  recordPaifuDecision(player, meta);
}

function recordCpuCallDecision(assessment, didCall) {
  if (!state.rules.cpuLearning || !assessment?.choice || !assessment.plan) return;
  const player = assessment.choice.player;
  if (player === "bottom" && !isCpuOnlyMode()) return;
  const taken = assessment.features;
  const skipped = { ...assessment.features, callTaken: 0, callSkipped: 1 };
  const features = didCall
    ? taken
    : skipped;
  const alternatives = didCall ? [skipped] : [taken];
  const decision = { player, features, alternatives };
  state.ai.decisions.push(decision);
  state.ai.roundDecisions.push(decision);
  recordPaifuDecision(player, {
    action: didCall ? assessment.choice.type : "スルー",
    tile: assessment.choice.tile,
    score: assessment.score,
    shanten: assessment.after,
    waits: assessment.postCall?.yakuWaitCount ?? 0,
    reason: didCall ? `${assessment.plan.name}狙い` : `${assessment.plan.name}候補を見送り`,
    alternatives: [{
      tile: assessment.choice.tile,
      score: assessment.score,
      shanten: assessment.after,
      reason: didCall ? "スルー候補" : `${assessment.choice.type}候補`,
    }],
  });
}

function learnFromGameResult() {
  if (!state.rules.cpuLearning || state.ai.decisions.length === 0) return;
  const ranked = getRankedPlayers();
  const rewards = Object.fromEntries(ranked.map((player, index) => [player, [1.0, 0.35, -0.35, -1.0][index]]));
  applyLearningBatch(state.ai.decisions, rewards, getLearningRate(0.004));
  state.ai.games += 1;
  const gameType = currentLearningGameType();
  state.ai.gamesByType[gameType] = (state.ai.gamesByType[gameType] ?? 0) + 1;
  state.ai.decisions = [];
  state.ai.roundDecisions = [];
  saveAiState();
}

function currentLearningGameType() {
  const type = state.currentPaifu?.rules?.gameType || state.currentGameType || state.gameType || state.rules.gameType;
  return type === "hanchan" ? "hanchan" : "tonpuu";
}

function learnFromRoundResult(scoreBefore, context = {}) {
  if (!state.rules.cpuLearning || state.ai.roundDecisions.length === 0) return;
  const rewards = Object.fromEntries(players.map((player) => {
    const scoreDelta = state.scores[player] - scoreBefore[player];
    const tenpaiBonus = context.tenpaiPlayers?.includes(player) ? 0.18 : 0;
    const agariBonus = context.winner === player ? 0.9 : 0;
    const dealInPenalty = context.discarder === player ? -0.75 : 0;
    return [player, Math.max(-1.4, Math.min(1.4, scoreDelta / 8000 + tenpaiBonus + agariBonus + dealInPenalty))];
  }));
  applyLearningBatch(state.ai.roundDecisions, rewards, getLearningRate(0.009));
  state.ai.roundDecisions = [];
  saveAiState();
}

function applyLearningBatch(decisions, rewards, rate) {
  if (!Array.isArray(decisions)) return;
  decisions.forEach((decision) => {
    const { player, features, alternatives = [] } = decision ?? {};
    if (!player || !features) return;
    const reward = rewards?.[player] ?? 0;
    adjustFeatureWeights(features, reward, rate);
    if (Array.isArray(alternatives)) {
      alternatives.forEach((alternative) => adjustFeatureWeights(alternative, -reward * 0.25, rate));
    }
  });
}

function adjustFeatureWeights(features, reward, rate) {
  if (!features || typeof features !== "object") return;
  state.ai.weights ??= defaultAiWeights();
  Object.entries(features).forEach(([key, value]) => {
    if (!Number.isFinite(value)) return;
    state.ai.weights[key] = clampWeight((state.ai.weights[key] ?? 0) + reward * value * rate);
  });
}

function getLearningRate(baseRate) {
  if (state.rules.learningMode === "fast") return baseRate * 3;
  if (state.rules.learningMode === "accelerated") return baseRate * 1.8;
  return baseRate;
}

function clampWeight(value) {
  return Math.max(-300, Math.min(300, Number(value.toFixed(4))));
}

function countPairs(counts) {
  return counts.filter((count) => count >= 2).length;
}

function countUsefulBlocks(counts) {
  let blocks = 0;
  for (let index = 0; index < 34; index += 1) {
    if (counts[index] >= 3) blocks += 2;
    else if (counts[index] >= 2) blocks += 1;
  }
  for (let suit = 0; suit < 3; suit += 1) {
    const start = suit * 9;
    for (let number = 0; number < 8; number += 1) {
      if (counts[start + number] > 0 && counts[start + number + 1] > 0) blocks += 1;
    }
    for (let number = 0; number < 7; number += 1) {
      if (counts[start + number] > 0 && counts[start + number + 2] > 0) blocks += 1;
    }
  }
  return blocks;
}

function countIsolatedTiles(hand) {
  const counts = countTiles(hand);
  return hand.filter((tile) => {
    const index = tile.tileIndex;
    if (counts[index] >= 2) return false;
    if (index >= 27) return true;
    const suitStart = Math.floor(index / 9) * 9;
    const pos = index - suitStart;
    return [-2, -1, 1, 2].every((offset) => {
      const other = pos + offset;
      return other < 0 || other > 8 || counts[suitStart + other] === 0;
    });
  }).length;
}

function discardSafetyPenalty(tile, handAfterDiscard) {
  const counts = countTiles(handAfterDiscard);
  if (tile.suit === "z" && counts[tile.tileIndex] === 0) return 5;
  if (tile.suit !== "z" && (tile.number === 1 || tile.number === 9)) return 3;
  return 0;
}

function getBestShantenForPlayer(player, hand = state.hands[player]) {
  return Math.min(getStandardShantenForPlayer(player, hand), getChiitoiShantenForPlayer(player, hand));
}

function getStandardShantenForPlayer(player, hand = state.hands[player]) {
  const fixedMelds = state.melds[player]?.length ?? 0;
  const counts = countTiles(hand);
  let best = 8;
  collectShantenBlocks(counts, 0, fixedMelds, 0, 0, false, (melds, taatsu, hasPair) => {
    const cappedTaatsu = Math.min(taatsu, 4 - melds);
    best = Math.min(best, 8 - melds * 2 - cappedTaatsu - (hasPair ? 1 : 0));
  });
  return best;
}

function getChiitoiShantenForPlayer(player, hand = state.hands[player]) {
  if ((state.melds[player]?.length ?? 0) > 0) return 8;
  const counts = countTiles(hand);
  const pairs = counts.filter((count) => count >= 2).length;
  const unique = counts.filter((count) => count > 0).length;
  return 6 - pairs + Math.max(0, 7 - unique);
}

function collectShantenBlocks(counts, start, melds, taatsu, pairs, hasPair, visit) {
  let index = start;
  while (index < 34 && counts[index] === 0) index += 1;
  if (index >= 34) {
    visit(melds, taatsu, hasPair);
    return;
  }

  if (counts[index] >= 3) {
    counts[index] -= 3;
    collectShantenBlocks(counts, index, melds + 1, taatsu, pairs, hasPair, visit);
    counts[index] += 3;
  }

  if (index < 27) {
    const suitStart = Math.floor(index / 9) * 9;
    const number = index - suitStart + 1;
    if (number <= 7 && counts[index + 1] > 0 && counts[index + 2] > 0) {
      counts[index] -= 1;
      counts[index + 1] -= 1;
      counts[index + 2] -= 1;
      collectShantenBlocks(counts, index, melds + 1, taatsu, pairs, hasPair, visit);
      counts[index] += 1;
      counts[index + 1] += 1;
      counts[index + 2] += 1;
    }
  }

  if (!hasPair && counts[index] >= 2) {
    counts[index] -= 2;
    collectShantenBlocks(counts, index, melds, taatsu, pairs + 1, true, visit);
    counts[index] += 2;
  }

  if (counts[index] >= 2) {
    counts[index] -= 2;
    collectShantenBlocks(counts, index, melds, taatsu + 1, pairs, hasPair, visit);
    counts[index] += 2;
  }

  if (index < 27) {
    const suitStart = Math.floor(index / 9) * 9;
    const number = index - suitStart + 1;
    if (number <= 8 && counts[index + 1] > 0) {
      counts[index] -= 1;
      counts[index + 1] -= 1;
      collectShantenBlocks(counts, index, melds, taatsu + 1, pairs, hasPair, visit);
      counts[index] += 1;
      counts[index + 1] += 1;
    }
    if (number <= 7 && counts[index + 2] > 0) {
      counts[index] -= 1;
      counts[index + 2] -= 1;
      collectShantenBlocks(counts, index, melds, taatsu + 1, pairs, hasPair, visit);
      counts[index] += 1;
      counts[index + 2] += 1;
    }
  }

  counts[index] -= 1;
  collectShantenBlocks(counts, index, melds, taatsu, pairs, hasPair, visit);
  counts[index] += 1;
}

function findRiichiDiscardIndex(player) {
  if (state.melds[player].length > 0 || state.hands[player].length !== 14 || state.scores[player] < 1000) return -1;
  const candidates = state.hands[player]
    .map((_, index) => ({ index, waits: waitsAfterDiscard(player, index) }))
    .filter((item) => item.waits.length > 0);
  if (candidates.length === 0) return -1;
  candidates.sort((a, b) => b.waits.length - a.waits.length);
  return candidates[0].index;
}

function shouldCpuRiichi(player, waits = []) {
  const features = getCpuRiichiFeatures(player, waits);
  const attackRate = { calm: 0.35, normal: 0.7, hard: 0.92 }[state.rules.cpuAttack] ?? 0.7;
  const needPointsBonus = shouldPreferPoints(player) ? 0.16 : 0;
  const topLatePenalty = isTopPlayer(player) && state.wall.length <= 30 ? 0.18 : 0;
  const waitBonus = waits.length >= 2 ? 0.08 : -0.06;
  const learnedBonus = Math.max(-0.18, Math.min(0.18, scoreCpuFeatures(features) / 1200));
  const rate = Math.max(0.08, Math.min(0.98, attackRate + needPointsBonus + waitBonus + learnedBonus - topLatePenalty));
  const declared = Math.random() < rate;
  recordCpuRiichiDecision(player, declared, features);
  return declared;
}

function getCpuRiichiFeatures(player, waits) {
  return {
    riichiDeclared: 1,
    riichiGoodWait: waits.length >= 2 ? 1 : 0,
    riichiBadWait: waits.length <= 1 ? 1 : 0,
    riichiNeedPoints: shouldPreferPoints(player) ? 1 : 0,
    riichiAsDealer: player === players[state.dealerIndex] ? 1 : 0,
    riichiTopLate: isTopPlayer(player) && state.wall.length <= 30 ? 1 : 0,
    ...getScoreSituationFeatures(player, "riichi"),
  };
}

function recordCpuRiichiDecision(player, declared, declaredFeatures) {
  if (!state.rules.cpuLearning) return;
  if (player === "bottom" && !isCpuOnlyMode()) return;
  const damaFeatures = { ...declaredFeatures, riichiDeclared: 0, damaChosen: 1 };
  const decision = {
    player,
    features: declared ? declaredFeatures : damaFeatures,
    alternatives: declared ? [damaFeatures] : [declaredFeatures],
  };
  state.ai.decisions.push(decision);
  state.ai.roundDecisions.push(decision);
  recordPaifuDecision(player, {
    action: declared ? "リーチ" : "ダマ",
    score: scoreCpuFeatures(declaredFeatures),
    shanten: 0,
    waits: declaredFeatures.riichiGoodWait ? 2 : 1,
    reason: declared ? "リーチ判断" : "闇聴判断",
  });
}

function recordPaifuDecision(player, meta = {}) {
  if (!state.currentPaifu || !currentPaifuRound()) return;
  recordPaifuEvent("decision", {
    player,
    action: meta.action ?? "判断",
    tile: meta.tile ?? null,
    reason: meta.reason ?? "",
    score: meta.score,
    shanten: meta.shanten,
    waits: meta.waits,
    alternatives: meta.alternatives ?? [],
  });
}

function keepsTenpaiAfterDiscard(player, tileIndex) {
  return waitsAfterDiscard(player, tileIndex).length > 0;
}

function waitsAfterDiscard(player, tileIndex) {
  if (state.hands[player].length % 3 !== 2) return [];
  const trial = state.hands[player].filter((__, index) => index !== tileIndex);
  return getWaitsForPlayer(player, trial);
}

function canCpuRiichi(player) {
  if (state.melds[player].length > 0 || state.hands[player].length !== 14 || state.scores[player] < 1000) return false;
  return state.hands[player].some((_, index) => {
    const trial = state.hands[player].filter((__, tileIndex) => tileIndex !== index);
    return getWaitsForPlayer(player, trial).length > 0;
  });
}

function getScoreSituationFeatures(player, prefix) {
  const rank = getPlayerRank(player);
  const topScore = Math.max(...players.map((seat) => state.scores[seat]));
  const ownScore = state.scores[player];
  const dealer = players[state.dealerIndex];
  const late = state.wall.length <= 30;
  const middleOrLater = state.wall.length <= 56;
  const entries = {
    AsDealer: player === dealer ? 1 : 0,
    IsTop: rank === 1 ? 1 : 0,
    IsLast: rank === 4 ? 1 : 0,
    NeedPoints: Math.max(0, (topScore - ownScore) / 10000),
    LeadPoints: Math.max(0, (ownScore - getSecondScoreFor(player)) / 10000),
    MiddleOrLater: middleOrLater ? 1 : 0,
    Late: late ? 1 : 0,
    OtherDealer: player !== dealer ? 1 : 0,
    WantsDealerFlow: player !== dealer && middleOrLater ? 1 : 0,
  };
  return Object.fromEntries(Object.entries(entries).map(([key, value]) => [`${prefix}${key}`, value]));
}

function shouldPreferSpeed(player) {
  return player !== players[state.dealerIndex] && (state.wall.length <= 56 || isTopPlayer(player));
}

function shouldPreferPoints(player) {
  return getPlayerRank(player) >= 3 || Math.max(...players.map((seat) => state.scores[seat])) - state.scores[player] >= 8000;
}

function isTopPlayer(player) {
  return getPlayerRank(player) === 1;
}

function getPlayerRank(player) {
  const ownScore = state.scores[player];
  return 1 + players.filter((seat) => state.scores[seat] > ownScore).length;
}

function getSecondScoreFor(player) {
  const lowerScores = players
    .filter((seat) => seat !== player)
    .map((seat) => state.scores[seat])
    .sort((a, b) => b - a);
  return lowerScores[0] ?? state.scores[player];
}

function nextPlayer(player) {
  return players[(players.indexOf(player) + 1) % players.length];
}

function sortHand(player) {
  state.hands[player].sort((a, b) => a.order - b.order || a.mark.localeCompare(b.mark, "ja"));
}
