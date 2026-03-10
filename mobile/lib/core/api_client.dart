import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ApiClient {
  late Dio dio;
  final SharedPreferences prefs;

  // Use 10.0.2.2 for Android emulator to host localhost, or localhost for iOS simulator
  // Since we don't know the exact env, we'll try to use a configurable base URL or default to 10.0.2.2 
  // which works on Android, or 127.0.0.1 which works on iOS. Let's use localhost, but configurable.
  static const String defaultBaseUrl = 'http://127.0.0.1:8000';

  ApiClient({required this.prefs, String baseUrl = defaultBaseUrl}) {
    dio = Dio(BaseOptions(
      baseUrl: baseUrl,
      receiveTimeout: const Duration(seconds: 15),
      connectTimeout: const Duration(seconds: 15),
    ));

    dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) {
        final token = prefs.getString('access_token');
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        return handler.next(options);
      },
      onError: (DioException e, handler) async {
        if (e.response?.statusCode == 401) {
          // Token expired, attempt refresh
          final refreshTokenStr = prefs.getString('refresh_token');
          if (refreshTokenStr != null) {
            try {
              // Create a separate dio instance to avoid interceptor loop
              final tokenDio = Dio(BaseOptions(baseUrl: baseUrl));
              final response = await tokenDio.post(
                '/v1/auth/refresh',
                data: {'refresh_token': refreshTokenStr},
              );
              
              if (response.statusCode == 200) {
                final newAccessToken = response.data['data']['access_token'];
                final newRefreshToken = response.data['data']['refresh_token'];
                
                await prefs.setString('access_token', newAccessToken);
                await prefs.setString('refresh_token', newRefreshToken);
                
                // Retry the original request
                final opts = e.requestOptions;
                opts.headers['Authorization'] = 'Bearer $newAccessToken';
                final retryResponse = await tokenDio.fetch(opts);
                return handler.resolve(retryResponse);
              }
            } catch (_) {
              // Refresh failed, clear tokens
              await prefs.remove('access_token');
              await prefs.remove('refresh_token');
            }
          }
        }
        return handler.next(e);
      },
    ));
  }
}
