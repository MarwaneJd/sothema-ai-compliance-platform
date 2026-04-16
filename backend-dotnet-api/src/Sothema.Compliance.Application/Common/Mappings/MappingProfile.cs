using AutoMapper;
using Sothema.Compliance.Application.DTOs;
using Sothema.Compliance.Domain.Entities;

namespace Sothema.Compliance.Application.Common.Mappings;

public class MappingProfile : Profile
{
    public MappingProfile()
    {
        CreateMap<Document, DocumentDto>()
            .ForMember(d => d.TextSegmentCount,
                opt => opt.MapFrom(src => src.TextSegments.Count))
            .ForMember(d => d.AnalysisCount,
                opt => opt.MapFrom(src => src.ComplianceAnalyses.Count));

        CreateMap<ComplianceAnalysis, ComplianceResultDto>()
            .ForMember(d => d.DocumentTitle,
                opt => opt.MapFrom(src => src.Document.Title))
            .ForMember(d => d.Status,
                opt => opt.MapFrom(src => src.Status.ToString()));

        CreateMap<AuditLog, AuditLogDto>();

        CreateMap<User, UserProfileDto>()
            .ForMember(d => d.Id,
                opt => opt.MapFrom(src => src.Id.ToString()))
            .ForMember(d => d.EntraObjectId,
                opt => opt.MapFrom(src => src.EntraObjectId))
            .ForMember(d => d.Role,
                opt => opt.MapFrom(src => src.Role.ToString()));
    }
}
