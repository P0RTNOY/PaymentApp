import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'transaction_provider.dart';

class TransactionDetailScreen extends StatefulWidget {
  final Map<String, dynamic> transaction;
  final TransactionProvider provider;

  const TransactionDetailScreen({
    super.key,
    required this.transaction,
    required this.provider,
  });

  @override
  State<TransactionDetailScreen> createState() => _TransactionDetailScreenState();
}

class _TransactionDetailScreenState extends State<TransactionDetailScreen> {
  bool _isIssuing = false;

  Future<void> _issueReceipt() async {
    setState(() => _isIssuing = true);
    final success = await widget.provider.issueDocument(widget.transaction['id']);
    
    if (mounted) {
      setState(() => _isIssuing = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            success ? 'Document issuance triggered.' : 'Failed to issue document.',
          ),
          backgroundColor: success ? Colors.green : Colors.red,
        ),
      );
      if (success) {
        Navigator.pop(context); // Go back after triggering
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final txn = widget.transaction;
    final amount = (txn['amount'] / 100).toStringAsFixed(2);
    final currency = txn['currency'] ?? 'ILS';
    final status = txn['status'] ?? 'unknown';
    final receiptState = txn['receiptState'] ?? 'none';
    
    DateTime? createdAt;
    if (txn['createdAt'] != null) {
      createdAt = DateTime.tryParse(txn['createdAt']);
    }
    
    final dateStr = createdAt != null 
      ? DateFormat.yMMMd().add_Hms().format(createdAt)
      : 'Unknown date';

    final isCompleted = status == 'completed';
    final canIssue = isCompleted && receiptState == 'none';

    return Scaffold(
      appBar: AppBar(title: const Text('Transaction Details')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header amount
            Center(
              child: Text(
                '$amount $currency',
                style: const TextStyle(fontSize: 36, fontWeight: FontWeight.bold),
              ),
            ),
            const SizedBox(height: 8),
            Center(
              child: Chip(
                label: Text(status.toUpperCase()),
                backgroundColor: isCompleted ? Colors.green.shade100 : Colors.orange.shade100,
              ),
            ),
            const SizedBox(height: 32),
            
            // Details card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  children: [
                    _buildRow('ID', txn['id']),
                    const Divider(),
                    _buildRow('Date', dateStr),
                    const Divider(),
                    _buildRow('Customer Email', txn['customerEmail'] ?? '-'),
                    const Divider(),
                    _buildRow('Customer Phone', txn['customerPhone'] ?? '-'),
                    const Divider(),
                    _buildRow('Provider', txn['providerType'] ?? '-'),
                    const Divider(),
                    _buildRow('Receipt State', receiptState.toUpperCase()),
                  ],
                ),
              ),
            ),
            
            const SizedBox(height: 32),
            
            // Actions
            if (canIssue)
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: _isIssuing ? null : _issueReceipt,
                  icon: _isIssuing
                      ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.receipt_long),
                  label: const Text('Issue Receipt'),
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 16),
                  ),
                ),
              )
            else if (receiptState == 'pending')
              const Center(
                child: Text('Receipt mapping is pending...', style: TextStyle(color: Colors.orange)),
              )
            else if (receiptState == 'issued')
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: () {
                    // Logic to download/view receipt if URL is stored. For MVP, just show toast.
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Viewing receipts is coming soon.')),
                    );
                  },
                  icon: const Icon(Icons.download),
                  label: const Text('Download Receipt'),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            flex: 2,
            child: Text(
              label,
              style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.grey),
            ),
          ),
          Expanded(
            flex: 3,
            child: Text(value, textAlign: TextAlign.right),
          ),
        ],
      ),
    );
  }
}
