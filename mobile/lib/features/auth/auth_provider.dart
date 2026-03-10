import 'package:flutter/material.dart';
import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../core/api_client.dart';

class AuthProvider extends ChangeNotifier {
  final ApiClient apiClient;
  final SharedPreferences prefs;

  bool _isInitializing = true;
  bool _isAuthenticated = false;
  String? _error;
  
  Map<String, dynamic>? _user;
  Map<String, dynamic>? _tenant;

  bool get isInitializing => _isInitializing;
  bool get isAuthenticated => _isAuthenticated;
  String? get error => _error;
  Map<String, dynamic>? get user => _user;
  Map<String, dynamic>? get tenant => _tenant;

  AuthProvider(this.apiClient, this.prefs) {
    _init();
  }

  Future<void> _init() async {
    final token = prefs.getString('access_token');
    if (token != null) {
      try {
        await _fetchMe();
        _isAuthenticated = true;
      } catch (e) {
        _isAuthenticated = false;
      }
    }
    _isInitializing = false;
    notifyListeners();
  }

  Future<void> _fetchMe() async {
    final response = await apiClient.dio.get('/v1/me');
    if (response.statusCode == 200) {
      _user = response.data['data']['user'];
      _tenant = response.data['data']['tenant'];
    }
  }

  Future<bool> login(String email, String password) async {
    _error = null;
    notifyListeners();
    try {
      final response = await apiClient.dio.post(
        '/v1/auth/login',
        data: {'email': email, 'password': password},
      );

      if (response.statusCode == 200) {
        final data = response.data['data'];
        await prefs.setString('access_token', data['access_token']);
        await prefs.setString('refresh_token', data['refresh_token']);
        
        await _fetchMe();
        _isAuthenticated = true;
        notifyListeners();
        return true;
      }
    } on DioException catch (e) {
      _error = e.response?.data?['error']?['message'] ?? e.message;
      notifyListeners();
    } catch (e) {
      _error = e.toString();
      notifyListeners();
    }
    return false;
  }

  Future<void> logout() async {
    try {
      await apiClient.dio.post('/v1/auth/logout');
    } catch (_) {}
    
    await prefs.remove('access_token');
    await prefs.remove('refresh_token');
    _isAuthenticated = false;
    _user = null;
    _tenant = null;
    notifyListeners();
  }
}
