Output .private/demo-release/terminal-compact-frames/
Output .private/demo-release/terminal-compact.txt

Require uv
Require sed

Set Shell bash
Set Width 1800
Set Height 1080
Set FontFamily "Menlo"
Set FontSize 24
Set Padding 28
Set Framerate 24
Set TypingSpeed 30ms
Set PlaybackSpeed 1

Env TERM "xterm-256color"
Env INPUTRC "/dev/null"

Type "sed -n '1,22p' fixtures/armadin/graphs/episode4-fortune600.json"
Enter
Wait+Line@5s /^>$/
Sleep 12s

Type "clear"
Enter
Wait+Line@5s /^>$/

Type "uv run --frozen python demo/run_demo.py"
Enter
Wait+Screen@60s /For the Fortune 600 chain reported/
Wait+Line@5s /^>$/
Sleep 38s

Type "clear"
Enter
Wait+Line@5s /^>$/

Type `sed -n '/"counts": {/,/^  }/p' demo/output/result.json`
Enter
Wait+Line@5s /^>$/
Sleep 10s

Type `sed -n '/"solution": {/,/^  }/p' demo/output/result.json`
Enter
Wait+Line@5s /^>$/
Sleep 15s
