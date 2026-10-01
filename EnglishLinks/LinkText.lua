local _, ns = ...

-- Pure transformation. All hyperlink payload bytes and surrounding text survive.
-- Cursor offsets, like EditBox:GetCursorPosition(), are UTF-8 byte offsets.
local function hasRandomSuffix(payload)
    local index = 0
    for field in (payload .. ":"):gmatch("([^:]*):") do
        index = index + 1
        if index == 8 then
            return field ~= "" and field ~= "0"
        end
    end
    return false
end

function ns.IsSafeName(name)
    return type(name) == "string" and #name > 0 and #name <= 255
        and not name:find("[%c|]")
end

function ns.Translate(text, names, overrides, cursor, onMissing)
    if type(text) ~= "string" then return text, cursor, 0 end
    local chunks, scan, changed = {}, 1, 0
    local mappedCursor = cursor
    while true do
        local first, last, payload, label = text:find("|H([^|]+)|h%[([^|]*)%]|h", scan)
        if not first then break end
        local itemID = tonumber(payload:match("^item:(%d+):"))
            or tonumber(payload:match("^item:(%d+)$"))
        -- A doubled pipe is literal text, not a hyperlink start.
        local pipes, p = 0, first - 1
        while p > 0 and text:sub(p, p) == "|" do pipes, p = pipes + 1, p - 1 end
        local name
        if itemID and pipes % 2 == 0 and not hasRandomSuffix(payload) then
            name = (overrides and overrides[itemID]) or names[itemID]
            if not ns.IsSafeName(name) then
                name = nil
                if onMissing then onMissing(itemID) end
            end
        end
        chunks[#chunks + 1] = text:sub(scan, first - 1)
        if name and name ~= label then
            chunks[#chunks + 1] = "|H" .. payload .. "|h[" .. name .. "]|h"
            changed = changed + 1
            -- Zero-based start/end offsets of the visible label in the raw text.
            local labelStart = first - 1 + 2 + #payload + 3
            local labelEnd = labelStart + #label
            if cursor then
                if cursor >= labelEnd then
                    mappedCursor = mappedCursor + #name - #label
                elseif cursor > labelStart then
                    mappedCursor = mappedCursor + labelStart + #name - cursor
                end
            end
        else
            chunks[#chunks + 1] = text:sub(first, last)
        end
        scan = last + 1
    end
    if changed == 0 then return text, cursor, 0 end
    chunks[#chunks + 1] = text:sub(scan)
    return table.concat(chunks), mappedCursor, changed
end

-- Generic path for typed links. Player names, custom labels and unknown types are
-- rejected by the resolver. Bracketed and plain displays retain their wrapper.
function ns.TranslateAll(text, resolve, cursor, onMissing)
    if type(text) ~= "string" then return text, cursor, 0 end
    local chunks, scan, count, mapped = {}, 1, 0, cursor
    while true do
        local first, last, payload, display = text:find("|H([^|]+)|h(.-)|h", scan)
        if not first then break end
        local bracketed = display:sub(1, 1) == "[" and display:sub(-1) == "]"
        local label = bracketed and display:sub(2, -2) or display
        -- The native map-pin label contains an atlas escape inside the link.
        -- Preserve only this known decoration; arbitrary markup remains untouched.
        local decoration = ""
        if payload:match("^worldmap:") then
            decoration = label:match("^(|A:Waypoint%-MapPin%-ChatIcon:[%d:%-]+|a%s*)") or ""
            label = label:sub(#decoration + 1)
        end
        local p, pipes = first - 1, 0
        while p > 0 and text:sub(p, p) == "|" do p, pipes = p - 1, pipes + 1 end
        local name = pipes % 2 == 0 and not label:find("|", 1, true) and resolve(payload, label, onMissing) or nil
        chunks[#chunks + 1] = text:sub(scan, first - 1)
        if ns.IsSafeName(name) and name ~= label then
            local replacement = decoration .. name
            replacement = bracketed and ("[" .. replacement .. "]") or replacement
            chunks[#chunks + 1] = "|H" .. payload .. "|h" .. replacement .. "|h"
            local start = first - 1 + 2 + #payload + 2 + (bracketed and 1 or 0) + #decoration
            local finish = start + #label
            if cursor then
                if cursor >= finish then mapped = mapped + #name - #label
                elseif cursor > start then mapped = mapped + start + #name - cursor end
            end
            count = count + 1
        else chunks[#chunks + 1] = text:sub(first, last) end
        scan = last + 1
    end
    if count == 0 then return text, cursor, 0 end
    chunks[#chunks + 1] = text:sub(scan)
    return table.concat(chunks), mapped, count
end
