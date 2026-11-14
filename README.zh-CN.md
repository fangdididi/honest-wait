# honest-wait（诚实的等待）

[English](README.md) | **简体中文**

一个智能体技能，专门处理每个产品里最后才被设计的部分：**任务运行时，用户看到的是什么。** 灵动岛式胶囊、Toast、进度条、状态栏、命令行 spinner、锁屏卡片、AI 智能体的"正在处理…"气泡，都在犯同样的错：按定时器前进的进度条、没人测量过的百分比、乱跳的剩余时间、一闪就没的"完成"、比任务活得还久的状态、伪装成实时活动的推广。

honest-wait 让等待变得**真实**（只声称系统真正知道的事）、**安静**（有变化才变化，只在用户必须行动时打扰）、**有始有终**（每个活动都以看得懂的状态结束，然后离开）。它附带一个小型回放检查器，读取录制的事件轨迹，给出 **STEADY（稳）/ SHAKY（晃）/ MISLEADING（误导）** 判定。

## 功能特点

- **等待卡**——在做任何 UI 之前，冻结活动内容、发起者、时长档位、显示区域、结束状态，以及少数允许打扰用户的事件。
- **名称 / 数字 / 下一步**——适用于任何界面的三个内容槽，并预先规划在极小区域里如何缩减。
- **进度诚实度阶梯（P0-P5）**——从"什么都不显示"到"以区间表示剩余时间"，每一级都要有证据才能使用；附带重试、最后 1%、停滞和剩余时间平滑的规则。
- **生命周期剧本**——每个应用事件对应一个界面动作：开始、更新、阶段、停滞、提问、提醒、完成、失败、取消、中断。
- **冲突规则**——成文的优先顺序、最多同时显示两个、同一来源轮流显示、不让任何活动被长期挤掉。
- **打扰与播报预算**——何时自动展开或震动、如何只在里程碑处对读屏软件播报、减少动态效果、共享界面上的隐私。
- **`honestwait.py` 回放检查器**——标记无声空档、进度倒退、卡在 99%、剩余时间乱跳、为进度打扰、播报泛滥、一闪而过、结尾消失太快或赖着不走、幽灵活动、无人请求的活动以及优先级问题。仅用 Python 标准库，无需安装。

## 安装

把整个文件夹复制到智能体的技能目录。

| 智能体 | 位置 |
|---|---|
| Claude Code | `~/.claude/skills/honest-wait/` 或 `<项目>/.claude/skills/honest-wait/` |
| Codex CLI | `~/.codex/skills/honest-wait/` |
| Cursor | `<项目>/.cursor/skills/honest-wait/` |
| GitHub Copilot | `<项目>/.github/skills/honest-wait/` |
| 其他智能体 | 任何会读取 `SKILL.md` 的位置，或直接把 `SKILL.md` 粘贴进系统提示词 |

```bash
git clone https://github.com/fangdididi/honest-wait.git ~/.claude/skills/honest-wait
```

## 使用方法

直接用自然语言告诉智能体，涉及实时状态和进度的工作会触发该技能：

- "给视频导出加一个实时状态胶囊，要诚实。"
- "上传进度条在 99% 停了半分钟——把这个等待修好。"
- "两个任务和一通来电共用顶部栏，谁优先？"
- "上线前帮我评审一下智能体的'思考中…'指示器。"

也可以自己运行检查器：

```bash
python3 honestwait.py init wait-card.json          # 生成空白等待卡
python3 honestwait.py demo demo-trace.jsonl        # 生成一条带问题的示例轨迹
python3 honestwait.py replay demo-trace.jsonl      # -> VERDICT: MISLEADING
python3 honestwait.py replay examples/steady-upload.jsonl --card wait-card.json   # -> STEADY
python3 honestwait.py replay trace.jsonl --json    # 机器可读输出；非 STEADY 时退出码为 1
```

轨迹文件每行一个 JSON 对象：

```json
{"t": 0.0, "id": "upload", "type": "start", "source": "user", "priority": 0}
{"t": 6.0, "id": "upload", "type": "update", "progress": 0.25, "units": [6, 24], "eta": 45}
{"t": 18.0, "id": "upload", "type": "update", "progress": 0.46, "units": [11, 24], "reason": "retrying photo 12"}
{"t": 38.0, "id": "upload", "type": "done"}
{"t": 41.0, "id": "upload", "type": "end"}
```

## 示例

```
honest-wait replay: 16 events, 3 activities
  WARN ETA_WHIPLASH     export     t=3.0     ETA jumped from ~58s to 20s within 2s; smooth it or show a range
  WARN ANNOUNCE_FLOOD   export     t=4.0     screen-reader announcement 3.0s after the last one; ...
  FAIL BACKWARDS        export     t=18.0    progress fell 30% -> 26% with no stated reason; ...
  FAIL ROUTINE_ALERT    export     t=18.0    alert on routine progress; ...
  WARN FLASH            sync       t=20.1    shown for 0.10s then gone; delay showing short tasks by ~0.4s
  FAIL UNASKED          promo      t=21.0    started by 'marketing': a live status surface is for ...
  WARN HANG_AT_99       export     t=25.0    sat at 99% for 15s; the last step needs its own stage label
  FAIL GHOST            promo      t=40.3    activity never ended; ...
  WARN VANISH           export     t=40.3    final state shown only 0.3s; hold it 1.0-8.0s
VERDICT: MISLEADING
```

含义：进度无故倒退、为常规进度打扰用户、一个营销"活动"占据界面且从不离开——任何一条 FAIL 都意味着不要上线。

## 文件结构

```
honest-wait/
├── SKILL.md                      # 技能说明（英文）
├── SKILL.zh-CN.md                # 技能说明（中文）
├── README.md                     # 英文说明
├── README.zh-CN.md               # 本文件
├── honestwait.py                 # 等待卡模板、示例轨迹、回放检查器
├── examples/
│   ├── steady-upload.jsonl       # 做对了的等待（来电、诚实的重试、看得清的结尾）
│   └── shaky-export.jsonl        # 做错了的等待
└── LICENSE
```

## 许可证

MIT © fangdididi
