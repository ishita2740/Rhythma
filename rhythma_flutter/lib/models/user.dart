class User {
  final String id;
  final String username;
  final String email;
  final String? fullName;

  User(
      {required this.id,
      required this.username,
      required this.email,
      this.fullName});

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'],
      username: json['username'],
      email: json['email'],
      fullName: json['full_name'],
    );
  }
}
