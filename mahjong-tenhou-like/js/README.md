# JavaScript の枝分け

このアプリはビルドなしで動かすため、`index.html` で下の順番に読み込んでいます。

- `core/state.js`: 牌定義、プレイヤー、共有状態
- `core/setup.js`: 対局開始、ルール設定、山生成
- `game/round-flow.js`: ツモ、打牌、CPU巡回、局進行
- `ai/cpu.js`: CPU打牌、向聴評価、学習
- `game/draw-flow.js`: 流局、ノーテン罰符、OK処理
- `ui/render.js`: 卓、手牌、河、中央表示、メニュー表示
- `game/actions.js`: リーチ、ロン、ツモ、副露、待ち表示
- `hand/hand-analysis.js`: 和了形、聴牌、待ち判定
- `scoring/agari.js`: 役、符、ドラ、点数、和了画面
- `game/results.js`: 次局、終局、順位、供託トップ取り
- `app.js`: ボタン接続と起動だけ
