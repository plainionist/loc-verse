open System
open System.IO
open System.Xml.Linq

module LinesOfCode =
    let countFile (file:string) =
        file
        |> File.ReadAllLines
        |> Seq.filter (fun x -> String.IsNullOrWhiteSpace(x) |> not)
        |> Seq.length

    let countFolder (folder:string) =
        Directory.GetFiles(folder, "*.cs", SearchOption.AllDirectories)
        |> Seq.sumBy countFile


type Project = {
    Name: string
    Assembly : string
    Location: string
    Dependencies: string list
    LinesOfCode: int
}

module Project =
    let getChildrenByName localName (x:XElement) =
        x.Elements()
        |> Seq.filter (fun x -> x.Name.LocalName = localName)

    let getReferences referenceType doc =
        doc
        |> getChildrenByName "ItemGroup"
        |> Seq.collect (getChildrenByName referenceType)
        |> Seq.map (fun x -> x.Attribute("Include").Value)

    let load (path:string) =
        path |> printfn "Loading %s ..."        
        
        let doc = XElement.Load(path)

        // example: "<Reference Include="Plainion.Windows, Version=3.0.0.0" />""
        let assemblyReferences = 
            doc
            |> getReferences "Reference"
            |> Seq.map (fun x -> x.Split(',')[0])

        // example: "<ProjectReference Include="..\Plainion.GraphViz.csproj" />""
        let projectReferences = 
            doc
            |> getReferences "ProjectReference"
            |> Seq.map Path.GetFileNameWithoutExtension

        let name = Path.GetFileNameWithoutExtension(path)

        {
            Name = name
            Location = path
            Assembly = 
                doc
                |> getChildrenByName "PropertyGroup"
                |> Seq.collect (getChildrenByName "AssemblyName")
                |> Seq.map (fun x -> x.Value)
                |> Seq.tryHead
                |> Option.defaultValue name
            Dependencies = 
                assemblyReferences
                |> Seq.append projectReferences
                |> Seq.distinctBy (fun x -> x.ToLower())
                |> List.ofSeq
            LinesOfCode = path |> Path.GetDirectoryName |> LinesOfCode.countFolder
        }

    // "module" is defined as top level folder in the workspace
    let getModuleName (workspace:string) project =
        Path.GetRelativePath(workspace, project.Location).Split(Path.DirectorySeparatorChar).[0]

module Analyzer =
    let memoize (fn:'a -> 'b) =
        let cache = new System.Collections.Concurrent.ConcurrentDictionary<'a,'b>()
        fun x -> cache.GetOrAdd(x, fn)

    let findProject projects name =
        projects
        |> List.tryFind (fun y -> y.Name.Equals(name, StringComparison.OrdinalIgnoreCase) 
                                 || y.Assembly.Equals(name, StringComparison.OrdinalIgnoreCase))
        |> Option.orElseWith (fun () -> printfn "WARNING: No project no for: %s" name; None)

    let rec getRecursiveDependencies findProject project =
        let dependencies = project.Dependencies |> List.choose findProject
        let indirectDependencies = dependencies |> List.collect (getRecursiveDependencies findProject)
        
        dependencies @ indirectDependencies

    let getLoCPerModule getModuleName projects =
        let findProject = findProject projects |> memoize

        projects
        |> Seq.groupBy getModuleName
        |> Seq.map (fun (name, moduleProjects) -> 
            let totalLoC =
                moduleProjects
                |> Seq.collect (getRecursiveDependencies findProject)
                |> Seq.append moduleProjects
                |> Seq.distinct
                |> Seq.sumBy (fun x -> x.LinesOfCode)
            name, totalLoC)
        |> List.ofSeq

module Report =
    let writePythonDictionary (file:string) items =
        use writer = new StreamWriter(file)
        writer.WriteLine("DATA  = {")
        
        items
        |> Seq.iter (fun (key, value) -> writer.WriteLine(sprintf "\t\"%s\": %i," key value))
        
        writer.WriteLine("}")


let ignoreProject (path:string) =
    let name = Path.GetFileNameWithoutExtension(path)
    name.EndsWith("Tests", StringComparison.OrdinalIgnoreCase)

let ignoreModule (name:string) =
    name.StartsWith("SDK")


let workspace = Path.GetFullPath(fsi.CommandLineArgs[1])
let output = Path.GetFullPath(fsi.CommandLineArgs[2])

printfn "Analyzing workspace: %s" workspace

Directory.GetFiles(workspace, "*.*proj", SearchOption.AllDirectories)
|> Seq.filter (ignoreProject >> not)
|> Seq.map Project.load
|> List.ofSeq
|> Analyzer.getLoCPerModule (Project.getModuleName workspace)
|> Seq.sortByDescending (fun x -> -snd x)
|> Seq.filter(fun (name,_) -> name |> ignoreModule |> not)
|> Report.writePythonDictionary output
