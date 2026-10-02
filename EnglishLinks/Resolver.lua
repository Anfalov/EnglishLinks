local _, ns = ...
ns.Kinds = {"item", "spell", "profession", "quest", "achievement", "currency",
    "companion", "talent", "mount"}
ns.ValidKind = {}
for _, kind in ipairs(ns.Kinds) do ns.ValidKind[kind] = true end
ns.Names = ns.Names or {}
ns.Names.item = ns.Names.item or {}
for id, name in pairs(ns.ItemNames or {}) do ns.Names.item[id] = name end
ns.PackMeta = ns.PackMeta or {}
if ns.ItemNamesMeta then ns.PackMeta.item = ns.ItemNamesMeta end
ns.Relations = ns.Relations or {}

function ns.Split(payload)
    local fields = {}
    for field in (payload .. ":"):gmatch("([^:]*):") do fields[#fields + 1] = field end
    return fields
end
local function positive(s)
    if type(s) ~= "string" or not s:match("^%d+$") then return nil end
    local n = tonumber(s)
    return n and n >= 1 and n <= 2147483647 and n or nil
end
local simple = {item="item", spell="spell", enchant="spell", quest="quest", achievement="achievement",
    currency="currency", nonbattlepet="companion", talent="talent", mount="mount"}
function ns.Describe(payload)
    local f = ns.Split(payload)
    local kind, id = simple[f[1]], positive(f[2])
    if f[1] == "trade" then
        -- Modern trade:GUID:spellID:skillLineID. Legacy trade:spellID:rank:maxRank:GUID:recipes.
        if f[2] and f[2]:match("^Player%-") then
            kind, id = "profession", positive(f[4])
            if not id then kind, id = "spell", positive(f[3]) end
        else kind, id = "spell", positive(f[2]) end
    elseif f[1] == "worldmap" then kind, id = "uimap", positive(f[2]) end
    if not kind or not id then return nil end
    return {kind=kind, id=id, rawType=f[1], fields=f, payload=payload}
end

function ns.SafeCall(fn, ...)
    if type(fn) ~= "function" then return nil end
    local results = {pcall(fn, ...)}
    if not results[1] then return nil end
    return unpack(results, 2)
end
local function api(namespace, method, ...) return ns.SafeCall(_G[namespace] and _G[namespace][method], ...) end
function ns.IsSecret(value) return issecretvalue and issecretvalue(value) end

function ns.InitDB(saved)
    saved.enabled = type(saved.enabled) == "boolean" and saved.enabled or saved.enabled == nil
    saved.overrides = type(saved.overrides) == "table" and saved.overrides or {}
    saved.typedOverrides = type(saved.typedOverrides) == "table" and saved.typedOverrides or {}
    saved.missing = type(saved.missing) == "table" and saved.missing or {}
    saved.types = type(saved.types) == "table" and saved.types or {}
    -- Retired in 0.4.2: remove their saved settings and stale missing IDs.
    for _, rawType in ipairs({"journal", "talentbuild", "instancelock"}) do
        saved.types[rawType] = nil
    end
    local retired = {specialization=true, journalinstance=true,
        journalencounter=true, journalsection=true, map=true}
    for kind in pairs(retired) do saved.typedOverrides[kind] = nil end
    for key in pairs(saved.missing) do
        if type(key) == "string" and retired[key:match("^([^:]+):")] then
            saved.missing[key] = nil
        end
    end
    for _, kind in ipairs(ns.Kinds) do
        if type(saved.typedOverrides[kind]) ~= "table" then saved.typedOverrides[kind] = {} end
    end
    -- 0.4.0 stored companion species overrides under the misleading battlepet name.
    for id, name in pairs(type(saved.typedOverrides.battlepet) == "table" and saved.typedOverrides.battlepet or {}) do
        if saved.typedOverrides.companion[id] == nil then saved.typedOverrides.companion[id] = name end
    end
    saved.typedOverrides.battlepet = nil
    -- Preserve the old public item overrides table for 0.1.0 users.
    for id, name in pairs(saved.overrides) do
        if saved.typedOverrides.item[id] == nil then saved.typedOverrides.item[id] = name end
    end
    saved.overrides = saved.typedOverrides.item
    ns.DB = saved
end

function ns.Lookup(kind, id, onMissing)
    if not id then return nil end
    local value = ns.DB.typedOverrides[kind] and ns.DB.typedOverrides[kind][id]
    if ns.IsSafeName(value) then return value end
    value = ns.Names[kind] and ns.Names[kind][id]
    if ns.IsSafeName(value) then return value end
    if onMissing then onMissing(kind, id) end
    return nil
end

function ns.Resolve(payload, label, onMissing)
    local d = ns.Describe(payload)
    if not d or ns.DB.types[d.rawType] == false then return nil end
    -- UiMapID identifies the coordinate system, not a visible zone title.
    if d.rawType == "worldmap" then return "Map Pin Location" end
    local name = ns.DB.typedOverrides[d.kind][d.id]
    if not ns.IsSafeName(name) then name = nil end
    -- mount: uses the summon SPELL ID, not the Mount DB2 row ID.
    -- Prefer a dedicated name if installed; the spell pack covers summon names.
    if not name and d.kind == "mount" then
        name = ns.Lookup("mount", d.id) or ns.Lookup("spell", d.id)
    end
    if not name and d.kind == "talent" then
        local ranks = ns.Relations.talent and ns.Relations.talent[d.id]
        local rank = tonumber(d.fields[3])
        local spellID = type(ranks) == "table" and ranks[math.max(0, rank or 0) + 1] or ranks
        if spellID and spellID > 0 then name = ns.Lookup("spell", spellID, onMissing) end
    end
    name = name or ns.Lookup(d.kind, d.id, onMissing)
    if not name then return nil end
    if d.kind == "item" then
        -- rand IDs are signed and use a separate namespace from bonus IDs.
        local suffix
        local rawRandom = d.fields[8]
        if rawRandom and rawRandom ~= "" then
            if not rawRandom:match("^%-?%d+$") then return nil end
            local randomID = tonumber(rawRandom)
            if not randomID or math.abs(randomID) > 2147483647 then return nil end
            if randomID ~= 0 then
                suffix = ns.ItemRandomAffixes and ns.ItemRandomAffixes[randomID]
                if not ns.IsSafeName(suffix) then return nil end
            end
        end
        -- Field 14 includes the leading "item" field in our split table.
        local rawCount = d.fields[14]
        local count = 0
        if rawCount and rawCount ~= "" then
            if not rawCount:match("^%d+$") then return nil end
            count = tonumber(rawCount)
            if count > 64 or #d.fields < 14 + count then return nil end
        end
        for i = 15, 14 + count do
            local bonusID = positive(d.fields[i])
            local value = bonusID and ns.ItemBonusSuffixes and ns.ItemBonusSuffixes[bonusID]
            -- Unknown bonuses might change the name. Never drop an unknown suffix.
            if value == nil then return nil end
            if value ~= "" then
                if suffix and suffix ~= value then return nil end
                suffix = value
            end
        end
        if suffix then name = name .. " " .. suffix end
    elseif d.rawType == "spell" then
        local subtext = api("C_Spell", "GetSpellSubtext", d.id)
        if not ns.IsSecret(subtext) and type(subtext) == "string" and subtext ~= "" then
            local tail = " (" .. subtext .. ")"
            local rank = subtext:match("(%d+)%s*$")
            if rank and label:sub(-#tail) == tail then name = name .. " (Rank " .. rank .. ")" end
        end
    end
    return ns.IsSafeName(name) and name or nil
end
