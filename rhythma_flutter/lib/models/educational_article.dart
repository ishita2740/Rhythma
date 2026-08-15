class EducationalArticle {
  final String id;
  final String title;
  final String summary;
  final String content;
  final String sourceName;
  final String sourceUrl;

  EducationalArticle({
    required this.id,
    required this.title,
    required this.summary,
    required this.content,
    required this.sourceName,
    required this.sourceUrl,
  });

  factory EducationalArticle.fromJson(Map<String, dynamic> json) {
    return EducationalArticle(
      id: json['id'] as String,
      title: json['title'] as String,
      summary: json['summary'] as String,
      content: json['content'] as String,
      sourceName: json['source_name'] as String,
      sourceUrl: json['source_url'] as String,
    );
  }
}
