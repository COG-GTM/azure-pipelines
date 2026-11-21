Runnable .NET 8 scaffold for the pricing-engine migration demo.
It provides a small ASP.NET Core pricing API with an xUnit test project.
Needs the .NET 8 SDK. From this directory, run `dotnet test PricingEngine.sln`, then
`dotnet run --project src/PricingEngine` and check http://localhost:5000/api/pricing/health
or `/api/pricing/catalog`.
