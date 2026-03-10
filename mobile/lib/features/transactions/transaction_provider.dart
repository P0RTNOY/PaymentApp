import 'package:flutter/material.dart';
import 'package:dio/dio.dart';
import '../../core/api_client.dart';

class TransactionProvider extends ChangeNotifier {
  final ApiClient apiClient;
  final String tenantId;

  final List<dynamic> _transactions = [];
  bool _isLoading = false;
  String? _error;
  String? _nextCursor;
  bool _hasMore = true;

  List<dynamic> get transactions => _transactions;
  bool get isLoading => _isLoading;
  String? get error => _error;
  bool get hasMore => _hasMore;

  TransactionProvider(this.apiClient, this.tenantId) {
    fetchTransactions();
  }

  Future<void> fetchTransactions({bool refresh = false}) async {
    if (_isLoading || (!refresh && !_hasMore)) return;

    _isLoading = true;
    _error = null;
    if (refresh) {
      _nextCursor = null;
      _transactions.clear();
      _hasMore = true;
    }
    notifyListeners();

    try {
      final queryParams = <String, dynamic>{'limit': 20};
      if (_nextCursor != null) {
        queryParams['cursor'] = _nextCursor;
      }

      final response = await apiClient.dio.get(
        '/v1/tenants/$tenantId/transactions',
        queryParameters: queryParams,
      );

      if (response.statusCode == 200) {
        final data = response.data['data'];
        final meta = response.data['meta'];

        final List<dynamic> newTxns = data;
        _transactions.addAll(newTxns);
        
        _nextCursor = meta['next_cursor'];
        _hasMore = meta['has_more'] ?? false;
      }
    } on DioException catch (e) {
      _error = e.response?.data?['error']?['message'] ?? e.message;
    } catch (e) {
      _error = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> issueDocument(String transactionId) async {
    try {
      final idempotencyKey = DateTime.now().millisecondsSinceEpoch.toString();
      final response = await apiClient.dio.post(
        '/v1/tenants/$tenantId/transactions/$transactionId/issue-document',
        options: Options(headers: {'Idempotency-Key': idempotencyKey}),
      );
      
      if (response.statusCode == 202) {
        // Optimistically update status in local list
        final index = _transactions.indexWhere((t) => t['id'] == transactionId);
        if (index != -1) {
          _transactions[index]['receiptState'] = 'pending';
          notifyListeners();
        }
        return true;
      }
    } catch (e) {
      // Ignore or handle
    }
    return false;
  }
}
