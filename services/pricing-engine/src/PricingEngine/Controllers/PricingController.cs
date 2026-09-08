using Microsoft.AspNetCore.Mvc;
using PricingEngine.Models;
using PricingEngine.Services;

namespace PricingEngine.Controllers;

[ApiController]
[Route("api/[controller]")]
public class PricingController : ControllerBase
{
    private readonly PricingService _pricingService;

    public PricingController(PricingService pricingService)
    {
        _pricingService = pricingService;
    }

    [HttpGet("catalog")]
    public IActionResult GetCatalog()
    {
        return Ok(_pricingService.GetCatalog());
    }

    [HttpPost("calculate")]
    public IActionResult CalculatePrice([FromBody] PriceRequest request)
    {
        try
        {
            var result = _pricingService.CalculatePrice(request);
            return Ok(result);
        }
        catch (KeyNotFoundException ex)
        {
            return NotFound(new { error = ex.Message });
        }
        catch (ArgumentException ex)
        {
            return BadRequest(new { error = ex.Message });
        }
    }

    [HttpPost("bulk")]
    public IActionResult CalculateBulkPrice([FromBody] BulkPriceRequest request)
    {
        try
        {
            var result = _pricingService.CalculateBulkPrice(request);
            return Ok(result);
        }
        catch (KeyNotFoundException ex)
        {
            return NotFound(new { error = ex.Message });
        }
        catch (ArgumentException ex)
        {
            return BadRequest(new { error = ex.Message });
        }
    }

    [HttpGet("health")]
    public IActionResult Health()
    {
        return Ok(new { status = "healthy", service = "pricing-engine" });
    }
}
