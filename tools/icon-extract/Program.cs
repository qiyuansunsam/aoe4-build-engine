using AOEMods.Essence.SGA.Graph;
using System.Text.Json;
using var input=File.OpenRead(args[0]);
var archive=Archive.FromStream(input);
var wanted=JsonSerializer.Deserialize<string[]>(File.ReadAllText(args[2]))!.ToHashSet(StringComparer.OrdinalIgnoreCase);
int count=0;
foreach(var node in ArchiveNodeHelper.EnumerateChildren(archive.Tocs[0].RootFolder).OfType<IArchiveFileNode>()) {
 var name=node.FullName.Replace('\\','/');
 if(!wanted.Contains(name))continue;
 var target=Path.Combine(args[1],name); Directory.CreateDirectory(Path.GetDirectoryName(target)!); File.WriteAllBytes(target,node.GetData().ToArray()); Console.WriteLine(name); count++;
}
Console.WriteLine($"Extracted {count}/{wanted.Count} requested UI icons");

