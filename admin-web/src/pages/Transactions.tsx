import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../core/AuthContext';
import { apiClient } from '../core/apiClient';

interface Transaction {
  id: string;
  tenantId: string;
  providerType: string;
  amount: number;
  currency: string;
  status: string;
  receiptState: string;
  customerEmail?: string;
  customerPhone?: string;
  createdAt: string;
}

export default function Transactions() {
  const { tenant } = useAuth();
  const navigate = useNavigate();
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);

  const fetchTransactions = async (cursor?: string) => {
    if (!tenant) return;
    
    setIsLoading(true);
    setError('');
    
    try {
      const params: any = { limit: 20 };
      if (cursor) params.cursor = cursor;
      
      const response = await apiClient.get(`/v1/tenants/${tenant.id}/transactions`, { params });
      const { data, meta } = response.data;
      
      if (cursor) {
        setTransactions(prev => [...prev, ...data]);
      } else {
        setTransactions(data);
      }
      
      setNextCursor(meta.next_cursor);
      setHasMore(meta.has_more);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || 'Failed to fetch transactions');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTransactions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenant]);

  return (
    <div className="px-4 sm:px-6 lg:px-8">
      <div className="sm:flex sm:items-center">
        <div className="sm:flex-auto">
          <h1 className="text-2xl font-semibold leading-6 text-gray-900">Transactions</h1>
          <p className="mt-2 text-sm text-gray-700">
            A list of all canonical transactions processed for this tenant.
          </p>
        </div>
      </div>
      
      {error && (
        <div className="mt-4 bg-red-50 p-4 rounded-md">
          <h3 className="text-sm font-medium text-red-800">Error</h3>
          <div className="mt-2 text-sm text-red-700">{error}</div>
        </div>
      )}

      <div className="mt-8 flow-root">
        <div className="-mx-4 -my-2 overflow-x-auto sm:-mx-6 lg:-mx-8">
          <div className="inline-block min-w-full py-2 align-middle sm:px-6 lg:px-8">
            <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 sm:rounded-lg">
              <table className="min-w-full divide-y divide-gray-300">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 sm:pl-6">Amount</th>
                    <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Status</th>
                    <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Customer</th>
                    <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Provider</th>
                    <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Receipt</th>
                    <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white">
                  {transactions.map((txn) => (
                    <tr 
                      key={txn.id} 
                      className="hover:bg-gray-50 cursor-pointer transition-colors"
                      onClick={() => navigate(`/transactions/${txn.id}`)}
                    >
                      <td className="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6">
                        {(txn.amount / 100).toFixed(2)} {txn.currency}
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                        <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${
                          txn.status === 'completed' 
                            ? 'bg-green-50 text-green-700 ring-green-600/20'
                            : 'bg-yellow-50 text-yellow-800 ring-yellow-600/20'
                        }`}>
                          {txn.status}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                        {txn.customerEmail || txn.customerPhone || 'Unknown'}
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                        {txn.providerType}
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                        {txn.receiptState}
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                        {new Date(txn.createdAt).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              
              {transactions.length === 0 && !isLoading && !error && (
                <div className="text-center py-12 text-gray-500 text-sm">
                  No transactions found.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
      
      {hasMore && (
        <div className="mt-6 flex justify-center pb-12">
          <button
            onClick={() => nextCursor && fetchTransactions(nextCursor)}
            disabled={isLoading}
            className="rounded-md bg-white px-3.5 py-2.5 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 disabled:opacity-50"
          >
            {isLoading ? 'Loading...' : 'Load More'}
          </button>
        </div>
      )}
    </div>
  );
}
