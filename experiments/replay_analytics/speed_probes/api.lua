-- Lists the game's script functions that could cut frame cost (camera, rendering, fog, UI, sim rate).
local pats = { "Camera", "Render", "FOW", "Fog", "SimRate", "Frame", "Draw", "Terrain", "UI_", "Game_", "Misc_", "Vis",
  "Cinematic", "Replay", "Sound", "LOD", "Setting", "Scar_", "Debug", "Toggle", "Hide", "Show", "Screen", "Window" }
local out = {}
for k, v in pairs(_G) do
  if type(k) == "string" and type(v) == "function" then
    for _, p in ipairs(pats) do
      if string.find(k, p, 1, true) then out[#out + 1] = k break end
    end
  end
end
table.sort(out)
local i = 1
while i <= #out do
  print("R|API|" .. table.concat(out, ",", i, math.min(i + 24, #out)))
  i = i + 25
end
print("R|PROBE|api " .. #out)
