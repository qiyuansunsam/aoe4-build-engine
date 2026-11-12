-- Every 5 game-seconds: game time, rendered frames, app frames (with the log's own wall stamps this gives frames per
-- second and sim ticks per frame). Once: every visibility-flag style constant the scripts can see.
function SP_Frames()
  print("R|PROBE|f|" .. RR_Time() .. "|" .. tostring(Game_GetRenderFrameCount()) .. "|" .. tostring(Game_GetAppFrameNumber()) .. "|" .. tostring(Game_GetSimRate()))
end
Rule_AddInterval(SP_Frames, 5)
local out = {}
for k, v in pairs(_G) do
  if type(k) == "string" and type(v) ~= "function" and type(v) ~= "table" then
    local u = string.upper(k)
    if string.find(u, "VIS", 1, true) or string.find(u, "GVF", 1, true) or string.find(u, "RENDER", 1, true) then
      out[#out + 1] = k .. "=" .. tostring(v)
    end
  end
end
table.sort(out)
local i = 1
while i <= #out do
  print("R|API|" .. table.concat(out, ",", i, math.min(i + 24, #out)))
  i = i + 25
end
print("R|PROBE|frames installed " .. #out)
