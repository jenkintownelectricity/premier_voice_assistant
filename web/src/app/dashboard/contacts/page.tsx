'use client';

import { useState, useEffect } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { HoneycombButton } from '@/components/HoneycombButton';
import { useAuth } from '@/lib/auth-context';
import { contactsApi } from '@/lib/api';

interface Contact {
  id: string;
  name: string;
  phone?: string;
  email?: string;
  company?: string;
  contact_type: string;
  permission_level: string;
  notes?: string;
  tags?: string[];
  total_calls: number;
  last_call_at?: string;
}

export default function ContactsPage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [editingContact, setEditingContact] = useState<Contact | null>(null);
  const [filter, setFilter] = useState<string>('');

  const [form, setForm] = useState({
    name: '',
    phone: '',
    email: '',
    company: '',
    contact_type: 'customer',
    permission_level: 'normal',
    notes: '',
  });

  const fetchContacts = async () => {
    if (!user?.id) return;
    try {
      const response = await contactsApi.getContacts(user.id, 100, 0, filter || undefined);
      setContacts(response.contacts);
    } catch (error) {
      console.error('Failed to load contacts:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchContacts();
  }, [user?.id, filter]);

  const openAddModal = () => {
    setEditingContact(null);
    setForm({ name: '', phone: '', email: '', company: '', contact_type: 'customer', permission_level: 'normal', notes: '' });
    setShowModal(true);
  };

  const openEditModal = (contact: Contact) => {
    setEditingContact(contact);
    setForm({
      name: contact.name,
      phone: contact.phone || '',
      email: contact.email || '',
      company: contact.company || '',
      contact_type: contact.contact_type,
      permission_level: contact.permission_level,
      notes: contact.notes || '',
    });
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!user?.id || !form.name) return;
    try {
      if (editingContact) {
        await contactsApi.updateContact(user.id, editingContact.id, form);
      } else {
        await contactsApi.createContact(user.id, form);
      }
      setShowModal(false);
      fetchContacts();
    } catch (error) {
      console.error('Failed to save contact:', error);
    }
  };

  const handleDelete = async (contactId: string) => {
    if (!user?.id) return;
    if (!confirm('Delete this contact?')) return;
    try {
      await contactsApi.deleteContact(user.id, contactId);
      fetchContacts();
    } catch (error) {
      console.error('Failed to delete:', error);
    }
  };

  const contactTypes = [
    { value: '', label: 'All' },
    { value: 'customer', label: 'Customers' },
    { value: 'lead', label: 'Leads' },
    { value: 'vendor', label: 'Vendors' },
    { value: 'team', label: 'Team' },
    { value: 'personal', label: 'Personal' },
  ];

  const permissionLevels = [
    { value: 'blocked', label: 'Blocked', color: 'bg-red-500' },
    { value: 'normal', label: 'Normal', color: 'bg-gray-500' },
    { value: 'vip', label: 'VIP', color: 'bg-gold' },
    { value: 'team', label: 'Team', color: 'bg-blue-500' },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gold text-xl">Loading contacts...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gold">Contacts</h1>
          <p className="text-gray-400 mt-1">Manage your business contacts</p>
        </div>
        <HoneycombButton onClick={openAddModal}>
          Add Contact
        </HoneycombButton>
      </div>

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        {contactTypes.map((type) => (
          <button
            key={type.value}
            onClick={() => setFilter(type.value)}
            className={`px-4 py-2 rounded-lg text-sm transition-colors ${
              filter === type.value
                ? 'bg-gold text-black'
                : 'bg-oled-gray text-gray-400 hover:bg-gray-800'
            }`}
          >
            {type.label}
          </button>
        ))}
      </div>

      {contacts.length === 0 ? (
        <Card>
          <CardContent>
            <div className="text-center py-12">
              <div className="text-6xl mb-4">contacts</div>
              <h3 className="text-xl text-white mb-2">No Contacts Yet</h3>
              <p className="text-gray-400 mb-6">Add contacts to organize your callers</p>
              <HoneycombButton onClick={openAddModal}>
                Add First Contact
              </HoneycombButton>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3">
          {contacts.map((contact) => (
            <div key={contact.id} onClick={() => openEditModal(contact)} className="cursor-pointer">
            <Card className="hover:border-gray-700 transition-colors">
              <CardContent>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-gold/10 rounded-full flex items-center justify-center text-gold text-lg font-bold">
                      {contact.name.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-semibold text-white">{contact.name}</span>
                        {contact.permission_level !== 'normal' && (
                          <span className={`px-2 py-0.5 text-xs rounded-full text-white ${
                            permissionLevels.find(p => p.value === contact.permission_level)?.color
                          }`}>
                            {contact.permission_level.toUpperCase()}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 text-sm text-gray-400">
                        {contact.phone && <span>{contact.phone}</span>}
                        {contact.company && <span>{contact.company}</span>}
                        <span className="px-2 py-0.5 bg-gray-800 rounded text-xs">{contact.contact_type}</span>
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm text-gray-400">{contact.total_calls} calls</div>
                    {contact.last_call_at && (
                      <div className="text-xs text-gray-500">
                        Last: {new Date(contact.last_call_at).toLocaleDateString()}
                      </div>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
            </div>
          ))}
        </div>
      )}

      {/* Add/Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-oled-dark border border-gray-800 rounded-2xl p-6 max-w-lg w-full max-h-[90vh] overflow-y-auto">
            <h2 className="text-2xl font-bold text-gold mb-4">
              {editingContact ? 'Edit Contact' : 'Add Contact'}
            </h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-2">Name *</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full bg-oled-gray border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-gold focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Phone</label>
                  <input
                    type="tel"
                    value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                    className="w-full bg-oled-gray border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-gold focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Email</label>
                  <input
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    className="w-full bg-oled-gray border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-gold focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-2">Company</label>
                <input
                  type="text"
                  value={form.company}
                  onChange={(e) => setForm({ ...form, company: e.target.value })}
                  className="w-full bg-oled-gray border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-gold focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Type</label>
                  <select
                    value={form.contact_type}
                    onChange={(e) => setForm({ ...form, contact_type: e.target.value })}
                    className="w-full bg-oled-gray border border-gray-700 rounded-lg px-4 py-3 text-white focus:border-gold focus:outline-none"
                  >
                    <option value="customer">Customer</option>
                    <option value="lead">Lead</option>
                    <option value="vendor">Vendor</option>
                    <option value="team">Team</option>
                    <option value="personal">Personal</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Permission</label>
                  <select
                    value={form.permission_level}
                    onChange={(e) => setForm({ ...form, permission_level: e.target.value })}
                    className="w-full bg-oled-gray border border-gray-700 rounded-lg px-4 py-3 text-white focus:border-gold focus:outline-none"
                  >
                    <option value="normal">Normal</option>
                    <option value="vip">VIP</option>
                    <option value="blocked">Blocked</option>
                    <option value="team">Team</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-2">Notes</label>
                <textarea
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  rows={3}
                  className="w-full bg-oled-gray border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-gold focus:outline-none resize-none"
                />
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <HoneycombButton variant="outline" onClick={() => setShowModal(false)}>
                Cancel
              </HoneycombButton>
              {editingContact && (
                <button
                  onClick={() => { handleDelete(editingContact.id); setShowModal(false); }}
                  className="px-4 py-2 text-red-500 hover:bg-red-500/10 rounded-lg transition-colors"
                >
                  Delete
                </button>
              )}
              <HoneycombButton onClick={handleSave}>
                {editingContact ? 'Save Changes' : 'Add Contact'}
              </HoneycombButton>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
