using AOEMods.Essence.Chunky;
using AOEMods.Essence.Chunky.RGD;
using AOEMods.Essence.SGA.Graph;
using System.Security.Cryptography;
using System.Text.Json;

if(args.Length==3 && args[0]=="--verify") {
 using var archiveStream=File.OpenRead(args[1]);
 var sourceArchive=Archive.FromStream(archiveStream);
 var sourceNodes=ArchiveNodeHelper.EnumerateChildren(sourceArchive.Tocs[0].RootFolder).OfType<IArchiveFileNode>()
   .ToDictionary(n=>n.FullName.Replace('\\','/'),StringComparer.OrdinalIgnoreCase);
 using var catalog=JsonDocument.Parse(File.ReadAllText(args[2]));
 var expected=new Dictionary<string,string>();
 void Visit(JsonElement element) {
   if(element.ValueKind==JsonValueKind.Object) {
     if(element.TryGetProperty("asset",out var asset) && element.TryGetProperty("sha256",out var hash))
       expected[asset.GetString()!]=hash.GetString()!;
     foreach(var property in element.EnumerateObject()) Visit(property.Value);
   } else if(element.ValueKind==JsonValueKind.Array) foreach(var child in element.EnumerateArray()) Visit(child);
 }
 Visit(catalog.RootElement);
 foreach(var (asset,hash) in expected) {
   if(!sourceNodes.TryGetValue(asset,out var node))throw new InvalidDataException("Missing archive record: "+asset);
   var actual=Convert.ToHexString(SHA256.HashData(node.GetData().ToArray())).ToLowerInvariant();
   if(actual!=hash)throw new InvalidDataException("Fingerprint mismatch: "+asset);
 }
 Console.WriteLine($"Verified {expected.Count} source fingerprints directly against installed archive");
 return;
}
if(args.Length != 2) throw new ArgumentException("GameExtract <Attrib.sga> <output-directory>");
using var input = File.OpenRead(args[0]);
var archive = Archive.FromStream(input);
var nodes = ArchiveNodeHelper.EnumerateChildren(archive.Tocs[0].RootFolder).OfType<IArchiveFileNode>().ToList();
var roots = new[]{"attrib/ebps/races/", "attrib/sbps/races/", "attrib/upgrade/", "attrib/weapon/", "attrib/racebps/", "attrib/data_version/", "attrib/resource_type_info/", "attrib/resource_sub_type/"};
// Decode every race, including variants. Playable/catalog scope is resolved by the normalizer.
var selected = nodes.Where(n => {var p=n.FullName.Replace('\\','/').ToLowerInvariant(); return p.EndsWith(".rgd") && roots.Any(p.StartsWith);}).ToList();
Directory.CreateDirectory(args[1]);
Console.WriteLine($"Selected {selected.Count} of {nodes.Count} archive records");
var evidence = new List<object>();
foreach(var n in selected) {
 var bytes=n.GetData().ToArray();
 using var stream=new MemoryStream(bytes);
 var decoded=GameDataJsonUtil.GameDataToJson(FormatReader.ReadRGD(stream));
 var relative=n.FullName.Replace('\\','/');
 var target=Path.Combine(args[1], Path.ChangeExtension(relative,"json"));
 Directory.CreateDirectory(Path.GetDirectoryName(target)!);
 File.WriteAllText(target,decoded);
 evidence.Add(new { asset=relative, sha256=Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant() });
 if(evidence.Count%250==0) Console.WriteLine($"Decoded {evidence.Count}/{selected.Count}");
}
File.WriteAllText(Path.Combine(args[1],"extraction-manifest.json"),JsonSerializer.Serialize(new {archive=args[0], archiveRecords=nodes.Count, selectedRecords=selected.Count, records=evidence}));
Console.WriteLine($"Complete: {evidence.Count} records");
