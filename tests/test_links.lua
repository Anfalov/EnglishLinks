local root = ...
local ns = {}
local tests = 0
local function equal(actual, expected, title)
    assert(actual == expected, (title or "assertion") .. ": expected " .. tostring(expected) .. ", got " .. tostring(actual))
    tests = tests + 1
end
assert(loadfile(root .. "/EnglishLinks/LinkText.lua"))("EnglishLinks", ns)
local names = { [6948] = "Hearthstone", [785] = "Mageroyal", [42] = "100% Test", [43] = "[PH] Test" }
local function link(id, name, tail)
    return "|cffffffff|Hitem:" .. id .. (tail or "::::::::::::") .. "|h[" .. name .. "]|h|r"
end
local russian = link(6948, "Камень возвращения")
local english = link(6948, "Hearthstone")
local translated, cursor, count = ns.Translate(russian, names, nil, #russian)
equal(translated, english, "Russian name")
equal(cursor, #english, "UTF-8 byte cursor")
equal(count, 1)
local payload = ":1900:12:23:34:45:0:987654:60:2:1:4:8:9"
equal(ns.Translate(link(6948, "Камень", payload), names), link(6948, "Hearthstone", payload), "All payload fields survive")
local suffix = link(6948, "Суффикс", ":0:0:0:0:0:-123:456")
equal(ns.Translate(suffix, names), suffix, "Random suffix is preserved untranslated")
local input = "До " .. russian .. " после " .. link(785, "Магороза") .. "."
local output = "До " .. english .. " после " .. link(785, "Mageroyal") .. "."
local actual, after, changes = ns.Translate(input, names, nil, #input)
equal(actual, output, "Multiple links")
equal(after, #output)
equal(changes, 2)
local beforeCursor = 2
local _, mapped = ns.Translate(input, names, nil, beforeCursor)
equal(mapped, beforeCursor, "Cursor before first link")
local middle = #("До " .. russian .. " после ")
_, mapped = ns.Translate(input, names, nil, middle)
equal(mapped, #("До " .. english .. " после "), "Cursor between links")
local labelStart = assert(russian:find("Камень", 1, true)) - 1
_, mapped = ns.Translate(russian, names, nil, labelStart + 2)
equal(mapped, labelStart + #"Hearthstone", "Cursor inside replaced label")
equal(ns.Translate(english, names), english, "Idempotent")
equal(ns.Translate(link(42, "Тест"), names), link(42, "100% Test"), "Percent is literal")
equal(ns.Translate(link(43, "Тест"), names), link(43, "[PH] Test"), "Brackets inside label")
equal(ns.Translate(russian, names, {[6948] = 'Custom "Stone"'}), link(6948, 'Custom "Stone"'), "Override")
equal(ns.Translate(russian, names, {[6948] = '|Hspell:1|h[X]|h'}), russian, "Unsafe override rejected")
local unknown = link(999999, "Неизвестно")
local missingID
equal(ns.Translate(unknown, names, nil, nil, function(id) missingID = id end), unknown)
equal(missingID, 999999)
for _, text in ipairs({"hello", "", "|Hspell:1|h[Заклинание]|h", "|Hquest:1:20|h[Квест]|h", "|Hitem:6948|h[unfinished", "||Hitem:6948|h[Literal]|h", "|Hbattlepet:1|h[Pet]|h"}) do
    equal(ns.Translate(text, names), text, "Untouched input")
end

-- Integration harness: WoW edit boxes, hooks, events and SavedVariables.
local frames, printed, errors = {}, {}, {}
local hooks = {}
_G.GetLocale = function() return "ruRU" end
_G.GetBuildInfo = function() return "1.60.1", "69977", "test", 16001 end
_G.DEFAULT_CHAT_FRAME = {AddMessage=function(_, msg) printed[#printed + 1] = msg end}
_G.SlashCmdList = {}
_G.NUM_CHAT_WINDOWS = 1
_G.geterrorhandler = function() return function(err) errors[#errors + 1] = err end end
_G.issecretvalue = function(x) return x == "SECRET" end
_G.hooksecurefunc = function(target, key, fn)
    if type(target) == "string" then fn, key, target = key, target, _G end
    local original = target[key]
    target[key] = function(...)
        local result = original(...)
        fn(...)
        return result
    end
end
local active
_G.ChatFrameUtil = {
    ActivateChat=function(box) active = box; box.focus = true end,
    GetActiveWindow=function() return active end,
    InsertLink=function(text)
        if active then active:Insert(text); return true end
        return false
    end
}
_G.CreateFrame = function()
    local frame = {scripts={}}
    function frame:RegisterEvent() end
    function frame:SetScript(event, fn) self.scripts[event] = fn end
    frames[#frames + 1] = frame
    return frame
end
local function box()
    local b = {text="", cursor=0, focus=true, maxBytes=0, maxLetters=0, hooks={}, writes=0}
    function b:HookScript(event, fn) self.hooks[#self.hooks + 1] = fn end
    function b:GetText() return self.text end
    function b:GetCursorPosition() return self.cursor end
    function b:SetCursorPosition(n) self.cursor = n end
    function b:HasFocus() return self.focus end
    function b:GetMaxBytes() return self.maxBytes end
    function b:GetMaxLetters() return self.maxLetters end
    function b:SetText(text)
        self.text = text
        self.writes = self.writes + 1
        assert(self.writes < 100, "Recursive text modification")
        for _, fn in ipairs(self.hooks) do fn(self) end
    end
    function b:Insert(text)
        local new = self.text:sub(1, self.cursor) .. text .. self.text:sub(self.cursor + 1)
        self.cursor = self.cursor + #text
        self:SetText(new)
    end
    return b
end
_G.ChatFrame1 = {editBox=box()}
_G.EnglishLinksDB = {enabled=true, overrides={}}
C_QuestLog = setmetatable({}, {__index=function() error("Unexpected quest API access") end})
ns.ItemNames = names
ns.ItemNamesMeta = {build="test",coverage="fixture"}
assert(loadfile(root .. "/EnglishLinks/Resolver.lua"))("EnglishLinks", ns)
assert(loadfile(root .. "/EnglishLinks/EnglishLinks.lua"))("EnglishLinks", ns)
local eventFrame = frames[1]
eventFrame.scripts.OnEvent(eventFrame, "ADDON_LOADED", "EnglishLinks")
eventFrame.scripts.OnEvent(eventFrame, "PLAYER_LOGIN")
equal(#ChatFrame1.editBox.hooks, 1, "Hook only once")
ChatFrameUtil.ActivateChat(ChatFrame1.editBox)
equal(ChatFrameUtil.InsertLink(russian), true, "Insert return preserved")
equal(ChatFrame1.editBox.text, english, "Realistic chat insertion")
equal(ChatFrame1.editBox.cursor, #english)
equal(ChatFrame1.editBox.writes, 2, "No recursion")
ns.Names.companion={[5005]='Musical Gustjumper'}
local petInput='|cffffd200|Hnonbattlepet:5005|h[Музыкальный ветроскок]|h|r'
local petExpected='|cffffd200|Hnonbattlepet:5005|h[Musical Gustjumper]|h|r'
local petBox=box()
ChatFrameUtil.ActivateChat(petBox)
equal(ChatFrameUtil.InsertLink(petInput),true,'Forever companion insert return')
equal(petBox.text,petExpected,'Observed Forever companion link')
equal(petBox.cursor,#petExpected,'Companion UTF-8 cursor')
SlashCmdList.ENGLISHLINKS('type nonbattlepet off')
petBox:SetText(petInput)
equal(petBox.text,petInput,'Companion command off')
SlashCmdList.ENGLISHLINKS('type nonbattlepet on')
petBox:SetText(petInput)
equal(petBox.text,petExpected,'Companion command on')
SlashCmdList.ENGLISHLINKS("off")
ChatFrame1.editBox:SetText(russian)
equal(ChatFrame1.editBox.text, russian, "Disabled")
SlashCmdList.ENGLISHLINKS("on")
local temporary = box()
ChatFrameUtil.ActivateChat(temporary)
ChatFrameUtil.InsertLink(russian)
equal(temporary.text, english, "Temporary chat box")
local limited = box()
limited.maxBytes = #link(42, "X")
ChatFrameUtil.ActivateChat(limited)
ChatFrameUtil.InsertLink(link(42, "X"))
equal(limited.text, link(42, "X"), "Byte limit: no truncation")
local inactive = box()
ChatFrameUtil.ActivateChat(inactive)
inactive.focus = false
inactive:SetText(russian)
equal(inactive.text, russian, "Unfocused box unchanged")
local hidden = box()
ChatFrameUtil.ActivateChat(hidden)
hidden:SetText("SECRET")
equal(hidden.text, "SECRET", "Secret text untouched")
SlashCmdList.ENGLISHLINKS("set 6948 Custom Hearthstone")
equal(EnglishLinksDB.overrides[6948], "Custom Hearthstone")
SlashCmdList.ENGLISHLINKS("unset 6948")
equal(EnglishLinksDB.overrides[6948], nil)
SlashCmdList.ENGLISHLINKS("status")
equal(#errors, 0, "No integration errors")
print(tests .. " Lua assertions passed")
