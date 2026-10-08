local addonName, ns = ...
local VERSION = "1.0.3"
local db, started
local attached = setmetatable({}, { __mode = "k" })
local changing = setmetatable({}, { __mode = "k" })
local changedCount, limitedCount = 0, 0
local hookedModern, hookedLegacy, hookedTemporary
local hookCount = 0
local ru = GetLocale() == "ruRU"
local function tr(russian, english) return ru and russian or english end
local function say(message)
    DEFAULT_CHAT_FRAME:AddMessage("|cff66ccffEnglishLinks:|r " .. message)
end
ns.Say = say
local function secret(value) return ns.IsSecret(value) end
local function missingCount()
    local count = 0
    for _ in pairs(db.missing) do count = count + 1 end
    return count
end
local function noteMissing(kind, id)
    local key = kind .. ":" .. id
    if not db.missing[key] and missingCount() < 1000 then
        db.missing[key] = true
    end
end

local function transformBox(box)
    if not db or not db.enabled or changing[box] or not box:HasFocus() then return end
    local text = box:GetText()
    if secret(text) or type(text) ~= "string" or not text:find("|H", 1, true) then return end
    local cursor = box:GetCursorPosition()
    if secret(cursor) then return end
    local converted, newCursor, count = ns.TranslateAll(text, ns.Resolve, cursor, noteMissing)
    if count == 0 then return end
    -- Never allow SetText to truncate a link or the user's message.
    local maxBytes = box.GetMaxBytes and box:GetMaxBytes() or 0
    local maxLetters = box.GetMaxLetters and box:GetMaxLetters() or 0
    local letters = strlenutf8 and strlenutf8(converted) or #converted
    if (maxBytes > 0 and #converted > maxBytes)
        or (maxLetters > 0 and letters > maxLetters) then
        limitedCount = limitedCount + 1
        return
    end
    changing[box] = true
    local ok, err = pcall(function()
        box:SetText(converted)
        box:SetCursorPosition(math.max(0, math.min(newCursor, #converted)))
    end)
    changing[box] = nil
    if ok then changedCount = changedCount + count
    else geterrorhandler()(err) end
end

local function attach(box)
    if not box or attached[box] or not box.HookScript or not box.GetText then return end
    attached[box] = true
    hookCount = hookCount + 1
    box:HookScript("OnTextChanged", transformBox)
end

local function attachAll()
    for i = 1, (NUM_CHAT_WINDOWS or 10) do
        local frame = _G["ChatFrame" .. i]
        attach((frame and frame.editBox) or _G["ChatFrame" .. i .. "EditBox"])
    end
    if CHAT_FRAMES then
        for _, name in ipairs(CHAT_FRAMES) do
            local frame = _G[name]
            if frame then attach(frame.editBox) end
        end
    end
    if CommunitiesFrame then attach(CommunitiesFrame.ChatEditBox) end
end

local function setupHooks()
    attachAll()
    -- Post-hooks do not replace Blizzard's insertion/dispatch functions.
    if not hookedModern and ChatFrameUtil and type(ChatFrameUtil.ActivateChat) == "function" then
        hooksecurefunc(ChatFrameUtil, "ActivateChat", function(box) attach(box) end)
        hookedModern = true
    end
    if not hookedLegacy and type(ChatEdit_ActivateChat) == "function" then
        hooksecurefunc("ChatEdit_ActivateChat", function(box) attach(box) end)
        hookedLegacy = true
    end
    if not hookedTemporary and type(FCF_OpenTemporaryWindow) == "function" then
        hooksecurefunc("FCF_OpenTemporaryWindow", attachAll)
        hookedTemporary = true
    end
end

local function coverage()
    for _, kind in ipairs(ns.Kinds) do
        local count = 0
        for _ in pairs(ns.Names[kind] or {}) do count = count + 1 end
        if count > 0 then
            local meta = ns.PackMeta[kind] or {}
            local source = tostring(meta.build or meta.sourceBuild or "community")
            if (meta.communityAdded or 0) > 0 then source = source .. "; community=" .. meta.communityAdded end
            if meta.coverage == "prepared" then
                say(kind .. ": database=" .. count)
            elseif meta.primaryCount then
                say(kind .. ": database=" .. count .. "; Wowhead Forever=" .. meta.primaryCount
                    .. "; fallback=" .. meta.fallbackCount .. "; snapshot=" .. meta.sourceDate)
            else
                say(kind .. ": database=" .. count .. "; build=" .. source)
            end
        end
    end
end
local function status()
    local version, build, _, interface = GetBuildInfo()
    say(VERSION .. "; " .. (db.enabled and "ON" or "OFF") .. "; " .. GetLocale()
        .. "; client=" .. tostring(version) .. "/" .. tostring(build) .. "; TOC=" .. tostring(interface))
    say("items=" .. tostring((ns.PackMeta.item or {}).count or 0) .. "; hooks=" .. hookCount
        .. "; changed=" .. changedCount .. "; missing=" .. missingCount() .. "; length-skips=" .. limitedCount)
    local absent = {}
    for _, kind in ipairs({"spell", "profession", "quest", "achievement"}) do
        if next(ns.Names[kind] or {}) == nil then absent[#absent + 1] = kind end
    end
    if #absent > 0 then say(tr("Базы ещё не загружены: ", "Databases not loaded: ") .. table.concat(absent, ", ")) end
    say("/el coverage")
end
local allowedTypes = {item=true,spell=true,enchant=true,trade=true,quest=true,achievement=true,
    currency=true,nonbattlepet=true,talent=true,worldmap=true,mount=true}
local function parseTarget(rest)
    local kind, id, name = rest:match("^(%a+)%s+(%d+)%s*(.*)$")
    if not kind then id, name = rest:match("^(%d+)%s*(.*)$"); kind = "item" end
    id = tonumber(id)
    if not ns.ValidKind[kind] or not id or id <= 0 or id > 2147483647 then return nil end
    return kind, id, name
end
local function command(message)
    local cmd, rest = (message or ""):match("^%s*(%S*)%s*(.-)%s*$")
    cmd = cmd:lower()
    if cmd == "on" or cmd == "off" then
        db.enabled = cmd == "on"; say(db.enabled and "ON" or "OFF")
    elseif cmd == "status" then status()
    elseif cmd == "coverage" then coverage()
    elseif cmd == "type" then
        local kind, mode = rest:match("^(%S+)%s+(%S+)$")
        if allowedTypes[kind] and (mode == "on" or mode == "off") then
            db.types[kind] = mode == "on"; say(kind .. " " .. mode)
        else say("/el type item|spell|enchant|trade|quest|achievement|currency|nonbattlepet|talent|worldmap|mount on|off") end
    elseif cmd == "missing" then
        local keys = {}
        for key in pairs(db.missing) do if type(key) == "string" then keys[#keys + 1] = key end end
        table.sort(keys)
        say(tr("Неизвестные ID (до 1000, сохраняются):", "Missing IDs (up to 1000, saved):"))
        for first = 1, #keys, 8 do
            local line = {}; for i = first, math.min(first + 7, #keys) do line[#line + 1] = keys[i] end
            say(table.concat(line, ", "))
        end
        if #keys == 0 then say("—") end
    elseif cmd == "set" or cmd == "unset" then
        local kind, id, name = parseTarget(rest)
        if kind and (cmd == "unset" or ns.IsSafeName(name)) then
            db.typedOverrides[kind][id] = cmd == "set" and name or nil
            local key = kind .. ":" .. id
            if db.missing[key] then db.missing[key] = nil end
            say(key .. (cmd == "set" and (" = " .. name) or ": override removed"))
        else say("/el set [kind] ID English name | /el unset [kind] ID") end
    else
        say("/el on | off | status | coverage | missing | set [kind] ID name | unset [kind] ID")
        say("/el type TYPE on|off")
    end
end

local frame = CreateFrame("Frame")
frame:RegisterEvent("ADDON_LOADED")
frame:RegisterEvent("PLAYER_LOGIN")
frame:SetScript("OnEvent", function(_, event, name)
    if event == "ADDON_LOADED" and name == addonName then
        if type(EnglishLinksDB) ~= "table" then EnglishLinksDB = {} end
        db = EnglishLinksDB
        ns.InitDB(db)
        SLASH_ENGLISHLINKS1, SLASH_ENGLISHLINKS2 = "/el", "/englishlinks"
        SlashCmdList.ENGLISHLINKS = command
        started = true
        setupHooks()
    elseif started and (event == "PLAYER_LOGIN" or event == "ADDON_LOADED") then
        setupHooks()
    end
end)
