import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../auth/auth_provider.dart';
import 'transaction_provider.dart';
import 'transaction_detail_screen.dart';

class TransactionListScreen extends StatelessWidget {
  const TransactionListScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.read<AuthProvider>();
    final tenantId = auth.tenant?['id'];

    if (tenantId == null) {
      return const Scaffold(body: Center(child: Text('No tenant found')));
    }

    return ChangeNotifierProvider(
      create: (_) => TransactionProvider(auth.apiClient, tenantId),
      child: const _TransactionListView(),
    );
  }
}

class _TransactionListView extends StatefulWidget {
  const _TransactionListView();

  @override
  State<_TransactionListView> createState() => _TransactionListViewState();
}

class _TransactionListViewState extends State<_TransactionListView> {
  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >= _scrollController.position.maxScrollExtent - 200) {
      context.read<TransactionProvider>().fetchTransactions();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Transactions'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => context.read<AuthProvider>().logout(),
          ),
        ],
      ),
      body: Consumer<TransactionProvider>(
        builder: (context, provider, child) {
          if (provider.transactions.isEmpty && provider.isLoading) {
            return const Center(child: CircularProgressIndicator());
          }

          if (provider.transactions.isEmpty && provider.error != null) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text('Error: ${provider.error}', style: const TextStyle(color: Colors.red)),
                  ElevatedButton(
                    onPressed: () => provider.fetchTransactions(refresh: true),
                    child: const Text('Retry'),
                  ),
                ],
              ),
            );
          }

          if (provider.transactions.isEmpty) {
            return const Center(child: Text('No transactions found.'));
          }

          return RefreshIndicator(
            onRefresh: () => provider.fetchTransactions(refresh: true),
            child: ListView.builder(
              controller: _scrollController,
              itemCount: provider.transactions.length + (provider.hasMore ? 1 : 0),
              itemBuilder: (context, index) {
                if (index == provider.transactions.length) {
                  return const Center(
                    child: Padding(
                      padding: EdgeInsets.all(16.0),
                      child: CircularProgressIndicator(),
                    ),
                  );
                }

                final txn = provider.transactions[index];
                final isCompleted = txn['status'] == 'completed';
                final amount = (txn['amount'] / 100).toStringAsFixed(2);
                final currency = txn['currency'] ?? 'ILS';
                
                return ListTile(
                  leading: CircleAvatar(
                    backgroundColor: isCompleted ? Colors.green.shade100 : Colors.orange.shade100,
                    child: Icon(
                      isCompleted ? Icons.check : Icons.pending,
                      color: isCompleted ? Colors.green : Colors.orange,
                    ),
                  ),
                  title: Text('$amount $currency'),
                  subtitle: Text(
                    txn['customerEmail'] ?? txn['customerPhone'] ?? 'Unknown Customer',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => TransactionDetailScreen(
                          transaction: txn,
                          provider: provider,
                        ),
                      ),
                    );
                  },
                );
              },
            ),
          );
        },
      ),
    );
  }
}
