function drawByButton() {
  if (state.current !== "bottom") return;
  if (state.awaitingDraw && state.hands.bottom.length === baseHandSize("bottom")) {
    draw("bottom");
    state.awaitingDraw = false;
    log("ツモりました。右端の牌、または手牌から1枚切ってください。");
    render();
  } else {
    log("打牌待ちです。牌をクリックして1枚切ってください。");
  }
}

function bindControls() {
  $("newRoundButton").addEventListener("click", openLobby);
  $("closeLobbyButton").addEventListener("click", closeLobby);
  $("startConfiguredGameButton").addEventListener("click", startGame);
  $("openPaifuButton").addEventListener("click", openPaifuViewer);
  $("closePaifuButton").addEventListener("click", closePaifuViewer);
  $("loadPaifuButton").addEventListener("click", loadPaifuByNumber);
  $("paifuRoundSelect").addEventListener("change", (event) => setPaifuViewerRound(event.target.value));
  $("paifuPrevButton").addEventListener("click", () => stepPaifuViewer(-1));
  $("paifuNextButton").addEventListener("click", () => stepPaifuViewer(1));
  $("paifuNumberInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") loadPaifuByNumber();
  });
  $("drawButton").addEventListener("click", drawByButton);
  $("tsumoButton").addEventListener("click", declareTsumo);
  $("ronButton").addEventListener("click", declareRon);
  $("kanButton").addEventListener("click", declareKan);
  $("noCallButton").addEventListener("click", toggleNoCallMode);
  $("autoWinButton").addEventListener("click", toggleAutoWin);
  $("riichiButton").addEventListener("click", declareRiichi);
  $("sortButton").addEventListener("click", () => {
    sortHand("bottom");
    log("理牌しました。");
    render();
  });
  $("endButton").addEventListener("click", openExitConfirm);
  $("playerButton").addEventListener("click", toggleViewSwitch);
  document.querySelectorAll("[data-view-seat]").forEach((button) => {
    button.addEventListener("click", () => setViewSeat(button.dataset.viewSeat));
  });
  $("roundButton").addEventListener("click", () => log(`${roundWind()}${state.round}局 ${state.honba}本場`));
  $("gameTypeButton").addEventListener("click", openLobby);
  $("pauseButton").addEventListener("click", pauseGame);
  $("resumeButton").addEventListener("click", resumeGame);
  $("stepButton").addEventListener("click", () => {
    if (state.current === "bottom") log("自分の番です。牌をクリックして打牌します。");
  });
  $("waitToggleButton").addEventListener("click", () => {
    state.waitDisplay = !state.waitDisplay;
    log(`待ち表示を${state.waitDisplay ? "オン" : "オフ"}にしました。`);
    render();
  });
  $("nextRoundButton").addEventListener("click", advanceAfterAgari);
  $("drawOkButton").addEventListener("click", () => pressDrawOk("bottom"));
  $("confirmExitButton").addEventListener("click", confirmExitToLobby);
  $("cancelExitButton").addEventListener("click", cancelExitConfirm);
  $("helpButton").addEventListener("click", () => log("操作: 自動ツモ後に牌クリックで打牌。ロン/槓/リーチ/待ち表示を使えます。"));
}

bindControls();
openLobby();
