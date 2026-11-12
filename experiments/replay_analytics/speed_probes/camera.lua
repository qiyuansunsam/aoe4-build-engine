-- Park the view on a map corner, zoomed in and looking straight down, so almost nothing is drawn. Re-applied every
-- 10 game-seconds in case replay playback moves the camera back. Prints what each call returned and where the camera is.
SP_CAM_N = 0
function SP_Try(name, ...)
  local f = _G[name]
  if type(f) ~= "function" then return name .. "=missing" end
  local ok, e = pcall(f, ...)
  return name .. "=" .. (ok and "ok" or ("ERR " .. tostring(e)))
end
function SP_Camera()
  local w, l = 0, 0
  pcall(function() w = World_GetWidth() l = World_GetLength() end)
  local pos = World_Pos(-(w / 2) + 6, 0, -(l / 2) + 6)
  local r = {}
  r[#r + 1] = SP_Try("Camera_SetInputEnabled", false)
  r[#r + 1] = SP_Try("Camera_ResetFocus")
  r[#r + 1] = SP_Try("Camera_MoveTo", pos, false)
  r[#r + 1] = SP_Try("Camera_SetDefaultZoomDist", 4)
  r[#r + 1] = SP_Try("Camera_SetZoomDist", 4)
  r[#r + 1] = SP_Try("Camera_SetDeclination", 89)
  SP_CAM_N = SP_CAM_N + 1
  if SP_CAM_N <= 3 or SP_CAM_N % 12 == 0 then
    local where = "?"
    pcall(function() local c = Camera_GetCurrentPos() local t = Camera_GetCurrentTargetPos() where = string.format("eye %.0f,%.0f,%.0f target %.0f,%.0f,%.0f zoom %.1f", c.x, c.y, c.z, t.x, t.y, t.z, Camera_GetZoomDist()) end)
    print("R|PROBE|cam|" .. RR_Time() .. "|world " .. w .. "x" .. l .. "|" .. table.concat(r, " ") .. "|" .. where)
  end
end
SP_Camera()
Rule_AddInterval(SP_Camera, 10)
print("R|PROBE|camera installed")
