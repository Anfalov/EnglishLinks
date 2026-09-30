local root = ...
local ns, checks = {}, 0
local function eq(a,b,label) assert(a==b,(label or '')..': '..tostring(a)..' ~= '..tostring(b)); checks=checks+1 end
local locale='ruRU'
GetLocale=function() return locale end
GetBuildInfo=function() return '1.60.1','70009' end
local frames, messages, now = {}, {}, 0
GetTime=function() return now end
CreateFrame=function()
    local f={scripts={}}
    function f:RegisterEvent() end
    function f:SetScript(event,fn) self.scripts[event]=fn end
    frames[#frames+1]=f; return f
end
for _,file in ipairs({'LinkText','Names_enUS','Resolver'}) do
    assert(loadfile(root..'/EnglishLinks/'..file..'.lua'))('EnglishLinks',ns)
end
ns.Say=function(s) messages[#messages+1]=s end
ns.InitDB({enabled=false,overrides={[1]='Old override'}})
eq(ns.DB.enabled,false,'preserve disabled');eq(ns.DB.typedOverrides.item[1],'Old override','migration')
ns.InitDB({})
for _,kind in ipairs(ns.Kinds) do ns.Names[kind]={[10]=kind..' English'} end
ns.Relations={talent={[20]={10,11}},recipe={[10]=10}}
ns.Names.spell[11]='Second rank'
local function link(payload,label,plain) return '|H'..payload..'|h'..(plain and label or '['..label..']')..'|h' end
local function translate(payload,label,plain) return ns.TranslateAll(link(payload,label or 'Русское',plain),ns.Resolve) end
local cases={
 {'item:10::::::::::::','item English'}, {'spell:10','spell English'},
 {'trade:10:1:300:GUID:bits','spell English'},
 {'trade:Player-1-AB:99:10','profession English'}, {'quest:10:60','quest English'},
 {'achievement:10:Player-1-A:1:0:0:0:0:0:0:0','achievement English'},
 {'currency:10:42','currency English'},
 {'talent:20:0','spell English'}, {'talent:20:1','Second rank'},
 {'worldmap:10:1234:5678','Map Pin: uimap English'}, {'mount:10','mount English'},
}
for _,c in ipairs(cases) do eq(translate(c[1]),link(c[1],c[2]),c[1]) end
-- Recipes retain the complete native link; English is outside its markup.
local native = '|cffffd000'..link('enchant:10','Профессия: Рецепт')..'|r'
local annotation = ' (profession English: spell English)'
local annotated = native..annotation
local result, cursor, changed = ns.TranslateAll(native,ns.Resolve,#native)
eq(result,annotated,'native recipe preserved byte-for-byte')
eq(cursor,#annotated,'recipe cursor after annotation')
eq(changed,1,'one recipe annotation')
local repeated, repeatCursor, repeatCount = ns.TranslateAll(annotated,ns.Resolve,#annotated)
eq(repeated,annotated,'annotation idempotent');eq(repeatCursor,#annotated);eq(repeatCount,0)
for _,position in ipairs({0,12,#native-3}) do
    local _,mapped = ns.TranslateAll(native,ns.Resolve,position)
    eq(mapped,position,'cursor before annotation stays put')
end
local multiple = 'До '..native..' и '..link('spell:10','Заклинание')..' / '..native
local expected = 'До '..annotated..' и '..link('spell:10','spell English')..' / '..annotated
local combined,mapped,total = ns.TranslateAll(multiple,ns.Resolve,#multiple)
eq(combined,expected,'recipes and spells coexist');eq(mapped,#expected);eq(total,3)
eq(translate('enchant:10','profession English: spell English'),link('enchant:10','profession English: spell English'),'English recipe needs no annotation')
eq(translate('enchant:10','Рецепт',true),link('enchant:10','Рецепт',true)..annotation,'plain label preserved')
eq(translate('enchant:999','Рецепт'),link('enchant:999','Рецепт'),'unknown recipe unchanged')
eq(ns.TranslateAll('|'..native:sub(11),ns.Resolve),'|'..native:sub(11),'escaped recipe unchanged')
ns.DB.types.enchant=false
eq(ns.TranslateAll(native,ns.Resolve),native,'recipe switch off')
ns.DB.types.enchant=true

-- Forever journal emits nonbattlepet:speciesID. No localized API is required.
C_PetJournal=nil
eq(translate('nonbattlepet:10'),link('nonbattlepet:10','companion English'),'Forever companion species')
eq(translate('nonbattlepet:999999'),link('nonbattlepet:999999','Русское'),'unknown companion preserved')
ns.DB.types.nonbattlepet=false
eq(translate('nonbattlepet:10'),link('nonbattlepet:10','Русское'),'companion switch')
ns.DB.types.nonbattlepet=true
ns.DB.typedOverrides.talent[20]='Chosen Talent'
eq(translate('talent:20:0'),link('talent:20:0','Chosen Talent'),'talent override')
ns.DB.types.spell=false;eq(translate('spell:10'),link('spell:10','Русское'),'per-type switch');ns.DB.types.spell=true
C_Spell={GetSpellSubtext=function() return 'Уровень 2' end,GetSpellName=function() return 'Русское' end}
eq(translate('spell:10','Огонь (Уровень 2)'),link('spell:10','spell English (Rank 2)'),'rank')
eq(translate('spell:10','Огонь'),link('spell:10','spell English'),'no invented rank')
eq(translate('spell:10','Русское',true),link('spell:10','spell English',true),'plain label')
local suff='item:10:0:0:0:0:0:-10:1234'
eq(translate(suff),link(suff,'Русское'),'suffix')
local prop='item:10:0:0:0:0:0:10:1234'
eq(translate(prop),link(prop,'Русское'),'property')
local unknown='item:10:0:0:0:0:0:-999:1234'
eq(translate(unknown),link(unknown,'Русское'),'unknown suffix keeps whole label')
C_PetJournal=setmetatable({}, {__index=function() error('No pet API needed') end})
eq(translate('battlepet:10:1:2:3:4:5:GUID','Вид питомца'),link('battlepet:10:1:2:3:4:5:GUID','Вид питомца'),'unsupported battlepet')
eq(translate('battlepet:10:1:2:3:4:5:GUID','Моя кличка'),link('battlepet:10:1:2:3:4:5:GUID','Моя кличка'),'custom pet name')
for _,p in ipairs({'player:Name','BNplayer:Name','url:http://x','clubFinder:10','outfit:10','spell:0','spell:-10','quest:bad','journal:9:10','journal:0:10:2','journal:1:10:2','journal:2:10:2','talentbuild:10:60:abcdef','instancelock:Player-1-A:10:1:999','instancelock:Player-1-A:0:1:999','unknown:10','battlePetAbil:10:1:2:3'}) do eq(translate(p),link(p,'Русское'),'unsupported '..p) end
local missing={}
local original=link('spell:777','Неизвестно')
eq(ns.TranslateAll(original,ns.Resolve,nil,function(k,id) missing[k..':'..id]=true end),original)
eq(missing['spell:777'],true);eq(ns.DB.learned,nil,'no learned cache created')
local mixed='До '..link('spell:10','Огонь')..' и '..link('quest:10','Задание')..' после'
local expected='До '..link('spell:10','spell English')..' и '..link('quest:10','quest English')..' после'
local result,cursor,count=ns.TranslateAll(mixed,ns.Resolve,#mixed)
eq(result,expected);eq(cursor,#expected);eq(count,2)
eq(ns.TranslateAll('|'..original,ns.Resolve),'|'..original,'escaped')
local texture='|Hspell:10|h|Ticon:16|tОгонь|h'
eq(ns.TranslateAll(texture,ns.Resolve),texture,'decorated label skipped')
-- Old learned data is retained for recovery, but never consulted or extended.
local legacy={quest={[901]={name='Old title',locale='enUS',build='1.60.1.70124'}}}
locale='enUS';ns.InitDB({learned=legacy, typedOverrides={quest={[902]='Manual title'}}})
C_QuestLog=setmetatable({}, {__index=function() error('Unexpected quest API access') end})
eq(ns.Lookup('quest',901),nil,'old learned title ignored')
eq(ns.DB.learned,legacy,'legacy data preserved')
eq(ns.Lookup('quest',902),'Manual title','manual override retained')
eq(ns.Lookup('spell',777),nil,'no English client fallback')
eq(ns.ValidKind.suffix,nil,'suffix category removed')
eq(ns.ValidKind.property,nil,'property category removed')
ns.InitDB({typedOverrides={battlepet={[5005]='Saved companion'}}})
eq(ns.Lookup('companion',5005),'Saved companion','migrate old species override')
ns.DB.typedOverrides.companion[5005]=nil
ns.InitDB(ns.DB)
eq(ns.Lookup('companion',5005),nil,'removed override stays removed after reload')
eq(ns.ValidKind.battlepet,nil,'no battlepet category')
eq(ns.ValidKind.petability,nil,'no pet ability category')
local retired = {'specialization','journalinstance','journalencounter','journalsection','map'}
local saved = {types={journal=true,talentbuild=false,instancelock=true,worldmap=false},
    typedOverrides={uimap={[10]='Kept map pin'},talent={[20]='Kept talent'}},
    missing={['uimap:999']=true,['spell:999']=true}}
for _,kind in ipairs(retired) do
    saved.typedOverrides[kind]={[10]='Obsolete'}
    saved.missing[kind..':10']=true
end
ns.InitDB(saved)
for _,kind in ipairs(retired) do
    eq(ns.ValidKind[kind],nil,'removed category '..kind)
    eq(saved.typedOverrides[kind],nil,'removed override '..kind)
    eq(saved.missing[kind..':10'],nil,'removed missing '..kind)
end
for _,rawType in ipairs({'journal','talentbuild','instancelock'}) do
    eq(saved.types[rawType],nil,'removed setting '..rawType)
end
eq(saved.types.worldmap,false,'map pin switch preserved')
eq(saved.missing['uimap:999'],true,'map pin missing preserved')
eq(saved.missing['spell:999'],true,'spell missing preserved')
eq(ns.Lookup('uimap',10),'Kept map pin','map pin override preserved')
eq(ns.Lookup('talent',20),'Kept talent','talent override preserved')
print(checks..' typed-link assertions passed')
